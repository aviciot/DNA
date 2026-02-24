--
-- PostgreSQL database dump
--

\restrict jVq5Ab84mOARzZdISWGMUTuviofMOBcnjHeIcNDjdW01ddZNpRtzTvmBcsBPm7L

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: dna_app; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA dna_app;


--
-- Name: cleanup_expired_sessions(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.cleanup_expired_sessions() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM auth.sessions WHERE expires_at < NOW();
END;
$$;


--
-- Name: update_roles_updated_at(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.update_roles_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: get_template_file_details(uuid); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.get_template_file_details(file_id uuid) RETURNS TABLE(id uuid, filename character varying, original_filename character varying, file_size_bytes bigint, description text, status character varying, uploaded_at timestamp with time zone, iso_codes text[], built_templates_count bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM dna_app.v_template_files_with_isos
    WHERE v_template_files_with_isos.id = file_id;
END;
$$;


--
-- Name: hard_delete_template_file(uuid, boolean); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.hard_delete_template_file(p_file_id uuid, p_force boolean DEFAULT false) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_template_count INTEGER;
BEGIN
    -- Count active templates
    SELECT COUNT(*) INTO v_template_count
    FROM dna_app.templates
    WHERE template_file_id = p_file_id
    AND status = 'active';

    -- Check if force is required
    IF v_template_count > 0 AND NOT p_force THEN
        RAISE EXCEPTION 'Cannot delete: % active templates depend on this file. Use force=true to delete anyway.', v_template_count;
    END IF;

    -- Delete (cascade will handle ai_tasks)
    DELETE FROM dna_app.template_files
    WHERE id = p_file_id;

    RETURN TRUE;
END;
$$;


--
-- Name: soft_delete_template_file(uuid, integer); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.soft_delete_template_file(p_file_id uuid, p_user_id integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Check if file has dependencies
    IF EXISTS (
        SELECT 1 FROM dna_app.templates
        WHERE template_file_id = p_file_id
        AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'Cannot delete: Active templates depend on this file';
    END IF;

    -- Soft delete
    UPDATE dna_app.template_files
    SET
        deleted_at = NOW(),
        deleted_by = p_user_id,
        status = 'deleted'
    WHERE id = p_file_id;

    RETURN TRUE;
END;
$$;


--
-- Name: sync_document_from_placeholder(); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.sync_document_from_placeholder() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    doc_record RECORD;
    total_keys INT;
    filled_keys INT;
    new_pct INT;
    new_status VARCHAR(50);
BEGIN
    -- Update every document that uses this template for this customer/plan
    FOR doc_record IN
        SELECT cd.id, cd.placeholder_fill_status, cd.mandatory_sections_total
        FROM dna_app.customer_documents cd
        WHERE cd.customer_id = NEW.customer_id
          AND cd.plan_id     = NEW.plan_id
          AND NEW.template_ids IS NOT NULL
          AND cd.template_id = ANY(NEW.template_ids)
    LOOP
        -- Update the JSONB fill status for this key
        UPDATE dna_app.customer_documents
        SET
            placeholder_fill_status = placeholder_fill_status ||
                jsonb_build_object(
                    NEW.placeholder_key,
                    CASE NEW.status
                        WHEN 'collected'   THEN 'filled'
                        WHEN 'auto_filled' THEN 'filled'
                        WHEN 'pending'     THEN 'pending'
                        ELSE 'pending'
                    END
                ),
            last_auto_filled_at = CASE
                WHEN NEW.status IN ('collected', 'auto_filled') THEN now()
                ELSE last_auto_filled_at
            END,
            updated_at = now()
        WHERE id = doc_record.id;

        -- Recalculate completion_percentage based on filled keys
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE value::text = '"filled"')
        INTO total_keys, filled_keys
        FROM jsonb_each(
            (SELECT placeholder_fill_status FROM dna_app.customer_documents WHERE id = doc_record.id)
        );

        IF total_keys > 0 THEN
            new_pct := ROUND((filled_keys::NUMERIC / total_keys) * 100);
        ELSE
            new_pct := 0;
        END IF;

        new_status := CASE
            WHEN new_pct = 100 THEN 'ready'
            WHEN new_pct > 0   THEN 'in_progress'
            ELSE 'not_started'
        END;

        UPDATE dna_app.customer_documents
        SET
            completion_percentage = new_pct,
            status = new_status
        WHERE id = doc_record.id;

    END LOOP;

    RETURN NEW;
END;
$$;


--
-- Name: sync_placeholder_from_task(); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.sync_placeholder_from_task() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Only sync tasks that are linked to a placeholder
    IF NEW.placeholder_key IS NULL OR NEW.plan_id IS NULL THEN
        RETURN NEW;
    END IF;

    UPDATE dna_app.customer_placeholders
    SET
        status = CASE NEW.status
            WHEN 'completed' THEN 'collected'
            WHEN 'pending'   THEN 'pending'
            WHEN 'cancelled' THEN 'pending'  -- cancelled task reopens placeholder
            ELSE status
        END,
        collected_at = CASE NEW.status
            WHEN 'completed' THEN COALESCE(collected_at, now())
            WHEN 'pending'   THEN NULL
            WHEN 'cancelled' THEN NULL
            ELSE collected_at
        END
    WHERE
        customer_id     = NEW.customer_id
        AND plan_id     = NEW.plan_id
        AND placeholder_key = NEW.placeholder_key
        -- Prevent loop: only update if placeholder status would actually change
        AND status IS DISTINCT FROM (
            CASE NEW.status
                WHEN 'completed' THEN 'collected'
                WHEN 'pending'   THEN 'pending'
                WHEN 'cancelled' THEN 'pending'
                ELSE status
            END
        );

    RETURN NEW;
END;
$$;


--
-- Name: sync_task_from_placeholder(); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.sync_task_from_placeholder() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Map placeholder status → task status
    UPDATE dna_app.customer_tasks
    SET
        status = CASE NEW.status
            WHEN 'collected'   THEN 'completed'
            WHEN 'auto_filled' THEN 'completed'
            WHEN 'pending'     THEN 'pending'
            ELSE status  -- unknown status: leave as-is
        END,
        completed_at = CASE NEW.status
            WHEN 'collected'   THEN COALESCE(completed_at, now())
            WHEN 'auto_filled' THEN COALESCE(completed_at, now())
            WHEN 'pending'     THEN NULL  -- revert clears completion
            ELSE completed_at
        END,
        updated_at = now()
    WHERE
        customer_id     = NEW.customer_id
        AND plan_id     = NEW.plan_id
        AND placeholder_key = NEW.placeholder_key
        AND status NOT IN ('cancelled');  -- never touch cancelled tasks

    RETURN NEW;
END;
$$;


--
-- Name: update_customer_config_updated_at(); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.update_customer_config_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_template_stats(uuid); Type: FUNCTION; Schema: dna_app; Owner: -
--

CREATE FUNCTION dna_app.update_template_stats(p_template_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    structure JSONB;
    fixed_cnt INT;
    fillable_cnt INT;
    tags TEXT[];
BEGIN
    -- Get template structure
    SELECT template_structure INTO structure
    FROM dna_app.templates
    WHERE id = p_template_id;

    IF structure IS NOT NULL THEN
        -- Count fixed sections
        fixed_cnt := COALESCE(jsonb_array_length(structure->'fixed_sections'), 0);

        -- Count fillable sections
        fillable_cnt := COALESCE(jsonb_array_length(structure->'fillable_sections'), 0);

        -- Extract semantic tags from metadata
        tags := COALESCE(
            (SELECT ARRAY(SELECT jsonb_array_elements_text(structure->'metadata'->'semantic_tags_used'))),
            ARRAY[]::TEXT[]
        );

        -- Update statistics
        UPDATE dna_app.templates
        SET
            total_fixed_sections = fixed_cnt,
            total_fillable_sections = fillable_cnt,
            semantic_tags = tags,
            updated_at = NOW()
        WHERE id = p_template_id;
    END IF;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: roles; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.roles (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    permissions jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_system boolean DEFAULT false NOT NULL
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.roles_id_seq OWNED BY auth.roles.id;


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sessions (
    id integer NOT NULL,
    session_id character varying(255) NOT NULL,
    user_id integer NOT NULL,
    access_token text NOT NULL,
    refresh_token text,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    ip_address inet,
    user_agent text,
    CONSTRAINT session_id_format CHECK (((session_id)::text ~ '^[a-f0-9-]+$'::text))
);


--
-- Name: sessions_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.sessions_id_seq OWNED BY auth.sessions.id;


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    role character varying(50) DEFAULT 'viewer'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login timestamp with time zone,
    role_id integer,
    CONSTRAINT email_format CHECK (((email)::text ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'::text)),
    CONSTRAINT role_valid CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'viewer'::character varying])::text[])))
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.users_id_seq OWNED BY auth.users.id;


--
-- Name: ai_prompts; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.ai_prompts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    prompt_key character varying(100) NOT NULL,
    prompt_text text NOT NULL,
    model character varying(100) DEFAULT 'gemini-1.5-pro'::character varying NOT NULL,
    max_tokens integer DEFAULT 32768 NOT NULL,
    temperature numeric(3,2) DEFAULT 0.2 NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: ai_tasks; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.ai_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_type character varying(50) NOT NULL,
    related_id uuid,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    progress integer DEFAULT 0,
    current_step text,
    llm_provider_id uuid,
    llm_provider character varying(50),
    llm_model character varying(100),
    result jsonb,
    error text,
    cost_usd numeric(10,4),
    tokens_input integer,
    tokens_output integer,
    duration_seconds integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_by integer,
    template_file_id uuid,
    trace_id uuid,
    template_id uuid,
    iso_standard_id uuid,
    CONSTRAINT progress_range CHECK (((progress >= 0) AND (progress <= 100))),
    CONSTRAINT status_valid CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT task_type_valid CHECK (((task_type)::text = ANY ((ARRAY['template_parse'::character varying, 'template_review'::character varying, 'document_generate'::character varying, 'analyze'::character varying, 'iso_build'::character varying])::text[])))
);


--
-- Name: customer_configuration; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_configuration (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer,
    config_type character varying(100) NOT NULL,
    config_key character varying(255) NOT NULL,
    config_value jsonb NOT NULL,
    is_template boolean DEFAULT false,
    template_variables jsonb,
    use_ai_phrasing boolean DEFAULT false,
    ai_tone character varying(50),
    ai_last_generated_at timestamp without time zone,
    ai_generation_prompt text,
    is_active boolean DEFAULT true,
    is_default boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    created_by integer,
    updated_at timestamp without time zone DEFAULT now(),
    updated_by integer
);


--
-- Name: TABLE customer_configuration; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_configuration IS 'Flexible configuration store for customer-specific settings, templates, and preferences';


--
-- Name: COLUMN customer_configuration.customer_id; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_configuration.customer_id IS 'NULL = global default configuration, INTEGER = customer-specific';


--
-- Name: COLUMN customer_configuration.template_variables; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_configuration.template_variables IS 'JSON array defining available variables for template interpolation';


--
-- Name: COLUMN customer_configuration.use_ai_phrasing; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_configuration.use_ai_phrasing IS 'Enable AI-powered content generation for this configuration';


--
-- Name: customer_documents; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer NOT NULL,
    plan_id uuid NOT NULL,
    template_id uuid NOT NULL,
    template_version integer,
    template_name character varying(500) NOT NULL,
    document_name character varying(500) NOT NULL,
    document_type character varying(100),
    iso_code character varying(50),
    status character varying(50) DEFAULT 'not_started'::character varying,
    content jsonb DEFAULT '{}'::jsonb NOT NULL,
    document_version integer DEFAULT 1,
    completion_percentage integer DEFAULT 0,
    mandatory_sections_total integer DEFAULT 0,
    mandatory_sections_completed integer DEFAULT 0,
    storage_path character varying(500),
    exported_at timestamp without time zone,
    assigned_to integer,
    created_by integer,
    updated_by integer,
    reviewed_by integer,
    approved_by integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    reviewed_at timestamp without time zone,
    approved_at timestamp without time zone,
    due_date date,
    notes text,
    placeholder_fill_status jsonb DEFAULT '{}'::jsonb,
    last_auto_filled_at timestamp without time zone
);


--
-- Name: TABLE customer_documents; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_documents IS 'Customer documents generated from templates';


--
-- Name: COLUMN customer_documents.template_version; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_documents.template_version IS 'Snapshot: template version used';


--
-- Name: COLUMN customer_documents.status; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_documents.status IS 'Status: not_started, in_progress, pending_review, approved, rejected';


--
-- Name: COLUMN customer_documents.content; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_documents.content IS 'Document structure with fixed and fillable sections';


--
-- Name: COLUMN customer_documents.placeholder_fill_status; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_documents.placeholder_fill_status IS 'Map of placeholder_key → {status: filled|empty|skipped, source: profile|manual|ai}';


--
-- Name: COLUMN customer_documents.last_auto_filled_at; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_documents.last_auto_filled_at IS 'Last time AI auto-filled placeholders from customer_profile_data.';


--
-- Name: customer_iso_plan_templates; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_iso_plan_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    template_id uuid NOT NULL,
    included boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    is_ignored boolean DEFAULT false,
    ignored_at timestamp without time zone,
    ignored_by integer,
    ignore_reason text
);


--
-- Name: TABLE customer_iso_plan_templates; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_iso_plan_templates IS 'Templates selected for each ISO plan (selective mode)';


--
-- Name: customer_iso_plans; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_iso_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer NOT NULL,
    iso_standard_id uuid NOT NULL,
    plan_name character varying(255),
    plan_status character varying(50) DEFAULT 'active'::character varying,
    template_selection_mode character varying(50) DEFAULT 'all'::character varying,
    target_completion_date date,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_by integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    is_ignored boolean DEFAULT false,
    ignored_at timestamp without time zone,
    ignored_by integer,
    ignore_reason text
);


--
-- Name: TABLE customer_iso_plans; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_iso_plans IS 'Customer ISO certification plans';


--
-- Name: COLUMN customer_iso_plans.plan_status; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_iso_plans.plan_status IS 'Status: active, paused, completed, cancelled';


--
-- Name: COLUMN customer_iso_plans.template_selection_mode; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_iso_plans.template_selection_mode IS 'Template selection: all or selective';


--
-- Name: COLUMN customer_iso_plans.is_ignored; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_iso_plans.is_ignored IS 'true = plan marked as irrelevant (but kept for history)';


--
-- Name: customer_placeholders; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_placeholders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer NOT NULL,
    plan_id uuid NOT NULL,
    placeholder_key character varying(255) NOT NULL,
    display_label character varying(500),
    data_type character varying(50) DEFAULT 'text'::character varying,
    is_required boolean DEFAULT true,
    status character varying(50) DEFAULT 'pending'::character varying,
    profile_data_id uuid,
    template_ids uuid[],
    collected_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: TABLE customer_placeholders; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_placeholders IS 'All unique placeholders needed for a customer plan. Linked to profile_data when collected.';


--
-- Name: customer_profile_data; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_profile_data (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer NOT NULL,
    field_key character varying(255) NOT NULL,
    field_value text,
    file_path character varying(1000),
    file_mime_type character varying(100),
    data_type character varying(50) DEFAULT 'text'::character varying NOT NULL,
    source character varying(50) DEFAULT 'manual'::character varying NOT NULL,
    confidence smallint DEFAULT 100,
    verified boolean DEFAULT false,
    collected_via_channel_id uuid,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: TABLE customer_profile_data; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_profile_data IS 'Shared pool of known facts per customer. One entry per field_key. Auto-fills all documents.';


--
-- Name: COLUMN customer_profile_data.confidence; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_profile_data.confidence IS '100=confirmed, <100=AI inferred, needs verification';


--
-- Name: customer_tasks; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customer_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    customer_id integer NOT NULL,
    plan_id uuid,
    document_id uuid,
    task_type character varying(50) NOT NULL,
    task_scope character varying(50) DEFAULT 'document'::character varying NOT NULL,
    section_id character varying(255),
    title character varying(500) NOT NULL,
    description text,
    status character varying(50) DEFAULT 'pending'::character varying,
    priority character varying(50) DEFAULT 'medium'::character varying,
    requires_evidence boolean DEFAULT false,
    evidence_description text,
    evidence_format character varying(100),
    evidence_uploaded boolean DEFAULT false,
    evidence_files jsonb,
    assigned_to integer,
    due_date date,
    completed_at timestamp without time zone,
    completed_by integer,
    created_by integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    notes text,
    auto_generated boolean DEFAULT false,
    is_ignored boolean DEFAULT false,
    ignored_at timestamp without time zone,
    ignored_by integer,
    ignore_reason text,
    created_manually_by integer,
    manual_task_context text,
    template_id uuid,
    placeholder_key character varying(255),
    answer text,
    answer_file_path character varying(1000),
    answered_at timestamp without time zone,
    answered_via character varying(50),
    collection_request_id uuid
);


--
-- Name: TABLE customer_tasks; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.customer_tasks IS 'Tasks for documents, customers, or ISO plans';


--
-- Name: COLUMN customer_tasks.task_type; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.task_type IS 'Type: fillable_section, evidence_required, review, custom, interview';


--
-- Name: COLUMN customer_tasks.task_scope; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.task_scope IS 'Scope: document, customer, iso_plan';


--
-- Name: COLUMN customer_tasks.status; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.status IS 'Status: pending, in_progress, blocked, completed, cancelled';


--
-- Name: COLUMN customer_tasks.priority; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.priority IS 'Priority: low, medium, high, urgent';


--
-- Name: COLUMN customer_tasks.auto_generated; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.auto_generated IS 'true = system generated from questions, false = manually created by admin';


--
-- Name: COLUMN customer_tasks.is_ignored; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.is_ignored IS 'true = task marked as irrelevant/ignored (e.g. template removed)';


--
-- Name: COLUMN customer_tasks.created_manually_by; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.created_manually_by IS 'User who manually created this task (NULL if auto-generated)';


--
-- Name: COLUMN customer_tasks.manual_task_context; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.manual_task_context IS 'Additional context for manual tasks';


--
-- Name: COLUMN customer_tasks.template_id; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.template_id IS 'Template that generated this task (NULL for customer/plan-level tasks)';


--
-- Name: COLUMN customer_tasks.placeholder_key; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.placeholder_key IS 'Which {{placeholder}} in the template this task is collecting data for.';


--
-- Name: COLUMN customer_tasks.answer; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customer_tasks.answer IS 'The collected answer. Written to customer_profile_data and document content on completion.';


--
-- Name: customers; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.customers (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    email character varying(255),
    contact_person character varying(255),
    phone character varying(50),
    address text,
    status character varying(50) DEFAULT 'active'::character varying NOT NULL,
    metadata jsonb,
    created_by integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    portal_username character varying(100),
    portal_password_hash character varying(255),
    contact_email character varying(255),
    document_email character varying(255),
    storage_type character varying(50) DEFAULT 'local'::character varying,
    storage_path character varying(500),
    storage_config jsonb,
    portal_enabled boolean DEFAULT false,
    last_portal_login timestamp without time zone,
    website character varying(500),
    compliance_email character varying(255),
    contract_email character varying(255),
    description text,
    CONSTRAINT status_valid CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'pending'::character varying, 'completed'::character varying])::text[])))
);


--
-- Name: COLUMN customers.portal_username; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.portal_username IS 'Username for customer portal access';


--
-- Name: COLUMN customers.portal_password_hash; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.portal_password_hash IS 'Hashed password for portal login';


--
-- Name: COLUMN customers.contact_email; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.contact_email IS 'Primary contact email for communication';


--
-- Name: COLUMN customers.document_email; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.document_email IS 'Email for sending/receiving documents';


--
-- Name: COLUMN customers.storage_type; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.storage_type IS 'Storage provider: local, google_drive, s3';


--
-- Name: COLUMN customers.storage_path; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.storage_path IS 'Path or URL to customer storage location';


--
-- Name: COLUMN customers.storage_config; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.storage_config IS 'Additional storage configuration (credentials, bucket names)';


--
-- Name: COLUMN customers.portal_enabled; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.portal_enabled IS 'Enable/disable customer portal access';


--
-- Name: COLUMN customers.last_portal_login; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.last_portal_login IS 'Last portal login timestamp';


--
-- Name: COLUMN customers.website; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.website IS 'Company website URL';


--
-- Name: COLUMN customers.compliance_email; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.compliance_email IS 'Email for receiving evidence/documents (automation)';


--
-- Name: COLUMN customers.contract_email; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.contract_email IS 'Email for contracts (CISO/Legal)';


--
-- Name: COLUMN customers.description; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.customers.description IS 'Optional notes/description about the customer';


--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: dna_app; Owner: -
--

CREATE SEQUENCE dna_app.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: dna_app; Owner: -
--

ALTER SEQUENCE dna_app.customers_id_seq OWNED BY dna_app.customers.id;


--
-- Name: iso_standards; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.iso_standards (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    requirements_summary text,
    active boolean DEFAULT true,
    display_order integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    color character varying(7) DEFAULT '#3b82f6'::character varying,
    ai_metadata jsonb
);


--
-- Name: COLUMN iso_standards.code; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON COLUMN dna_app.iso_standards.code IS 'ISO standard code (format: "ISO XXXXX:YYYY" or "stand_alone" for non-ISO templates)';


--
-- Name: llm_providers; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.llm_providers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    model character varying(100) NOT NULL,
    api_key_env character varying(100) NOT NULL,
    cost_per_1k_input numeric(10,4),
    cost_per_1k_output numeric(10,4),
    max_tokens integer DEFAULT 4096,
    enabled boolean DEFAULT true,
    is_default_parser boolean DEFAULT false,
    is_default_reviewer boolean DEFAULT false,
    is_default_chat boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT provider_name_valid CHECK (((name)::text ~ '^[a-z0-9_-]+$'::text))
);


--
-- Name: task_resolutions; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.task_resolutions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid NOT NULL,
    resolution_type character varying(50) NOT NULL,
    resolution_data jsonb,
    is_final boolean DEFAULT false,
    requires_approval boolean DEFAULT false,
    approved_at timestamp without time zone,
    approved_by integer,
    quality_score integer,
    completeness_score integer,
    resolved_by integer,
    resolved_at timestamp without time zone DEFAULT now(),
    follow_up_required boolean DEFAULT false,
    follow_up_task_id uuid,
    notes text,
    attachments jsonb,
    CONSTRAINT task_resolutions_completeness_score_check CHECK (((completeness_score >= 0) AND (completeness_score <= 100))),
    CONSTRAINT task_resolutions_quality_score_check CHECK (((quality_score >= 1) AND (quality_score <= 5)))
);


--
-- Name: TABLE task_resolutions; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.task_resolutions IS 'Track how tasks are resolved, including answers, evidence, approvals, etc.';


--
-- Name: task_templates; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.task_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    template_name character varying(255) NOT NULL,
    template_description text,
    task_type character varying(100) NOT NULL,
    task_scope character varying(50) NOT NULL,
    default_title character varying(500),
    default_description text,
    default_priority character varying(50) DEFAULT 'medium'::character varying,
    default_due_in_days integer,
    checklist_items jsonb,
    is_active boolean DEFAULT true,
    is_system_template boolean DEFAULT false,
    usage_count integer DEFAULT 0,
    last_used_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE task_templates; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON TABLE dna_app.task_templates IS 'Reusable templates for creating manual tasks quickly';


--
-- Name: template_files; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.template_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    filename character varying(255) NOT NULL,
    original_filename character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_size_bytes bigint NOT NULL,
    file_hash character varying(64),
    mime_type character varying(100) DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character varying,
    description text,
    version character varying(50) DEFAULT '1.0'::character varying,
    notes text,
    status character varying(50) DEFAULT 'uploaded'::character varying NOT NULL,
    uploaded_by integer,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    archived_at timestamp with time zone,
    iso_standard_id uuid,
    file_type character varying(50) DEFAULT 'reference'::character varying,
    deleted_at timestamp with time zone,
    deleted_by integer,
    CONSTRAINT file_size_positive CHECK ((file_size_bytes > 0)),
    CONSTRAINT file_type_valid CHECK (((file_type)::text = ANY ((ARRAY['reference'::character varying, 'template'::character varying, 'generated'::character varying])::text[]))),
    CONSTRAINT status_valid CHECK (((status)::text = ANY ((ARRAY['uploaded'::character varying, 'archived'::character varying, 'deleted'::character varying])::text[])))
);


--
-- Name: template_iso_mapping; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.template_iso_mapping (
    template_id uuid NOT NULL,
    iso_standard_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by integer
);


--
-- Name: template_iso_standards; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.template_iso_standards (
    template_id uuid NOT NULL,
    iso_standard_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: template_versions; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.template_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    template_id uuid NOT NULL,
    version_number integer NOT NULL,
    template_structure jsonb NOT NULL,
    change_summary text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by integer,
    restored_from_version integer
);


--
-- Name: templates; Type: TABLE; Schema: dna_app; Owner: -
--

CREATE TABLE dna_app.templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    iso_standard character varying(50),
    template_file_id uuid,
    template_structure jsonb NOT NULL,
    status character varying(50) DEFAULT 'draft'::character varying NOT NULL,
    version character varying(50) DEFAULT '1.0'::character varying,
    total_fixed_sections integer DEFAULT 0,
    total_fillable_sections integer DEFAULT 0,
    semantic_tags text[] DEFAULT ARRAY[]::text[],
    ai_task_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    approved_at timestamp with time zone,
    approved_by integer,
    created_by integer,
    version_number integer DEFAULT 1 NOT NULL,
    last_edited_at timestamp with time zone DEFAULT now(),
    last_edited_by integer,
    restored_from_version integer,
    CONSTRAINT template_status_valid CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'approved'::character varying, 'archived'::character varying])::text[])))
);


--
-- Name: v_customer_iso_progress; Type: VIEW; Schema: dna_app; Owner: -
--

CREATE VIEW dna_app.v_customer_iso_progress AS
 SELECT cip.id,
    cip.customer_id,
    cip.iso_standard_id,
    iso.code AS iso_code,
    iso.name AS iso_name,
    cip.plan_name,
    cip.plan_status,
    cip.target_completion_date,
    count(DISTINCT ipt.template_id) AS total_templates,
    count(DISTINCT
        CASE
            WHEN ((cd.status)::text = 'completed'::text) THEN cd.template_id
            ELSE NULL::uuid
        END) AS completed_templates,
    count(DISTINCT
        CASE
            WHEN ((cd.status)::text = ANY ((ARRAY['in_progress'::character varying, 'draft'::character varying])::text[])) THEN cd.template_id
            ELSE NULL::uuid
        END) AS in_progress_templates,
    count(DISTINCT ct.id) FILTER (WHERE (ct.is_ignored = false)) AS total_tasks,
    count(DISTINCT ct.id) FILTER (WHERE (((ct.status)::text = 'completed'::text) AND (ct.is_ignored = false))) AS completed_tasks,
    count(DISTINCT ct.id) FILTER (WHERE (((ct.status)::text = 'in_progress'::text) AND (ct.is_ignored = false))) AS in_progress_tasks,
    count(DISTINCT ct.id) FILTER (WHERE (((ct.status)::text = 'pending'::text) AND (ct.is_ignored = false))) AS pending_tasks,
    count(DISTINCT ct.id) FILTER (WHERE (ct.is_ignored = true)) AS ignored_tasks,
        CASE
            WHEN (count(DISTINCT ct.id) FILTER (WHERE (ct.is_ignored = false)) = 0) THEN 0
            ELSE ((((count(DISTINCT ct.id) FILTER (WHERE (((ct.status)::text = 'completed'::text) AND (ct.is_ignored = false))))::double precision / (count(DISTINCT ct.id) FILTER (WHERE (ct.is_ignored = false)))::double precision) * (100)::double precision))::integer
        END AS progress_percentage,
    cip.created_at,
    cip.updated_at
   FROM ((((dna_app.customer_iso_plans cip
     LEFT JOIN dna_app.iso_standards iso ON ((cip.iso_standard_id = iso.id)))
     LEFT JOIN dna_app.customer_iso_plan_templates ipt ON ((cip.id = ipt.plan_id)))
     LEFT JOIN dna_app.customer_documents cd ON (((cip.id = cd.plan_id) AND (cip.customer_id = cd.customer_id))))
     LEFT JOIN dna_app.customer_tasks ct ON ((cip.id = ct.plan_id)))
  WHERE ((cip.is_ignored = false) OR (cip.is_ignored IS NULL))
  GROUP BY cip.id, cip.customer_id, cip.iso_standard_id, iso.code, iso.name, cip.plan_name, cip.plan_status, cip.target_completion_date, cip.created_at, cip.updated_at;


--
-- Name: VIEW v_customer_iso_progress; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON VIEW dna_app.v_customer_iso_progress IS 'Customer progress tracking per ISO standard (excluding ignored tasks)';


--
-- Name: v_customer_overall_progress; Type: VIEW; Schema: dna_app; Owner: -
--

CREATE VIEW dna_app.v_customer_overall_progress AS
 SELECT c.id AS customer_id,
    c.name AS company_name,
    c.email AS contact_email,
    c.portal_enabled,
    c.last_portal_login,
    count(DISTINCT p.id) AS total_iso_plans,
    count(DISTINCT
        CASE
            WHEN ((p.plan_status)::text = 'active'::text) THEN p.id
            ELSE NULL::uuid
        END) AS active_plans,
    count(DISTINCT
        CASE
            WHEN ((p.plan_status)::text = 'completed'::text) THEN p.id
            ELSE NULL::uuid
        END) AS completed_plans,
    count(DISTINCT d.id) AS total_documents,
    count(DISTINCT
        CASE
            WHEN ((d.status)::text = 'approved'::text) THEN d.id
            ELSE NULL::uuid
        END) AS approved_documents,
    count(DISTINCT t.id) AS total_tasks,
    count(DISTINCT
        CASE
            WHEN ((t.status)::text = 'completed'::text) THEN t.id
            ELSE NULL::uuid
        END) AS completed_tasks,
    round(
        CASE
            WHEN (count(DISTINCT d.id) > 0) THEN COALESCE(avg(d.completion_percentage), (0)::numeric)
            ELSE (0)::numeric
        END, 2) AS avg_document_completion,
    c.created_at AS customer_since
   FROM (((dna_app.customers c
     LEFT JOIN dna_app.customer_iso_plans p ON ((c.id = p.customer_id)))
     LEFT JOIN dna_app.customer_documents d ON ((p.id = d.plan_id)))
     LEFT JOIN dna_app.customer_tasks t ON ((c.id = t.customer_id)))
  GROUP BY c.id, c.name, c.email, c.portal_enabled, c.last_portal_login, c.created_at;


--
-- Name: VIEW v_customer_overall_progress; Type: COMMENT; Schema: dna_app; Owner: -
--

COMMENT ON VIEW dna_app.v_customer_overall_progress IS 'Overall progress for all customers across ISO plans';


--
-- Name: v_reference_documents; Type: VIEW; Schema: dna_app; Owner: -
--

CREATE VIEW dna_app.v_reference_documents AS
SELECT
    NULL::uuid AS id,
    NULL::character varying(255) AS filename,
    NULL::character varying(255) AS original_filename,
    NULL::text AS file_path,
    NULL::bigint AS file_size_bytes,
    NULL::character varying(64) AS file_hash,
    NULL::character varying(100) AS mime_type,
    NULL::text AS description,
    NULL::character varying(50) AS version,
    NULL::text AS notes,
    NULL::character varying(50) AS status,
    NULL::integer AS uploaded_by,
    NULL::timestamp with time zone AS uploaded_at,
    NULL::timestamp with time zone AS updated_at,
    NULL::timestamp with time zone AS archived_at,
    NULL::uuid AS iso_standard_id,
    NULL::character varying(50) AS file_type,
    NULL::timestamp with time zone AS deleted_at,
    NULL::integer AS deleted_by,
    NULL::character varying(50) AS iso_standard_code,
    NULL::character varying(200) AS iso_standard_name,
    NULL::character varying(255) AS uploaded_by_email,
    NULL::bigint AS template_count,
    NULL::bigint AS analysis_count;


--
-- Name: v_template_files_with_details; Type: VIEW; Schema: dna_app; Owner: -
--

CREATE VIEW dna_app.v_template_files_with_details AS
SELECT
    NULL::uuid AS id,
    NULL::character varying(255) AS filename,
    NULL::character varying(255) AS original_filename,
    NULL::text AS file_path,
    NULL::bigint AS file_size_bytes,
    NULL::text AS description,
    NULL::character varying(50) AS status,
    NULL::timestamp with time zone AS uploaded_at,
    NULL::character varying(255) AS uploaded_by_email,
    NULL::bigint AS built_templates_count;


--
-- Name: v_templates_with_versions; Type: VIEW; Schema: dna_app; Owner: -
--

CREATE VIEW dna_app.v_templates_with_versions AS
SELECT
    NULL::uuid AS id,
    NULL::character varying(255) AS name,
    NULL::text AS description,
    NULL::character varying(50) AS iso_standard,
    NULL::uuid AS template_file_id,
    NULL::jsonb AS template_structure,
    NULL::character varying(50) AS status,
    NULL::integer AS version_number,
    NULL::integer AS total_fixed_sections,
    NULL::integer AS total_fillable_sections,
    NULL::text[] AS semantic_tags,
    NULL::timestamp with time zone AS created_at,
    NULL::timestamp with time zone AS updated_at,
    NULL::timestamp with time zone AS approved_at,
    NULL::timestamp with time zone AS last_edited_at,
    NULL::integer AS last_edited_by,
    NULL::character varying(255) AS last_edited_by_email,
    NULL::bigint AS total_versions;


--
-- Name: roles id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.roles ALTER COLUMN id SET DEFAULT nextval('auth.roles_id_seq'::regclass);


--
-- Name: sessions id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions ALTER COLUMN id SET DEFAULT nextval('auth.sessions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users ALTER COLUMN id SET DEFAULT nextval('auth.users_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customers ALTER COLUMN id SET DEFAULT nextval('dna_app.customers_id_seq'::regclass);


--
-- Data for Name: roles; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.roles (id, name, description, permissions, created_at, is_system) FROM stdin;
1	admin	Administrator with full access	{"tabs": ["dashboard", "customers", "documents", "admin", "iam"], "chatwidget": true}	2026-02-05 22:55:42.97176+00	t
2	viewer	Viewer with read-only access	{"tabs": ["dashboard", "customers", "documents"], "chatwidget": true}	2026-02-05 22:55:42.97176+00	t
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sessions (id, session_id, user_id, access_token, refresh_token, expires_at, created_at, ip_address, user_agent) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.users (id, email, password_hash, full_name, role, is_active, created_at, updated_at, last_login, role_id) FROM stdin;
1	admin@dna.local	$2b$12$lsarDE/VAQIN5QOLHikcDeC1eu4oajV5Na6EK/b.6l7XmwhxWoPGG	DNA Administrator	admin	t	2026-02-05 22:55:42.983095+00	2026-02-24 10:12:59.314657+00	2026-02-24 10:12:59.314657+00	1
\.


--
-- Data for Name: ai_prompts; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.ai_prompts (id, prompt_key, prompt_text, model, max_tokens, temperature, description, is_active, updated_at) FROM stdin;
ddef1437-2cd8-469d-b93f-c9a19009531e	iso_build	You are a compliance documentation expert. You will receive the full text of an ISO standard.\n\nYour task is to produce:\n1. A concise SUMMARY of the standard\n2. A complete set of OPERATIONAL PROCEDURE TEMPLATES — each one is a REAL DOCUMENT with placeholder gaps\n\nSTRICT RULES:\n- Use ONLY content from the provided ISO text. Do not add, invent, or interpret.\n- Preserve original ISO clause and control IDs exactly (e.g. 4.1, A.5.1, 8.2.3)\n- Every organization-specific value MUST become a {{placeholder_key}} embedded directly in the document text\n- Use lowercase_underscore for placeholder keys (e.g. {{organization_name}}, {{ciso_role}})\n- Group related controls into logical standalone procedure documents\n- Each fillable section MUST include its ISO reference (clause or control ID)\n\nDOCUMENT STRUCTURE REQUIREMENT:\n- fixed_sections contain the actual document text with {{placeholders}} embedded inline\n- Example: "This policy applies to {{organization_name}} and all employees under the supervision of {{ciso_role}}."\n- fillable_sections describe EACH placeholder that appears in the document — one entry per unique placeholder key\n- The "placeholder" field in each fillable_section MUST exactly match a {{key}} used in fixed_sections content\n- Every fillable_section MUST have a "question" field — a clear, specific question to ask the customer to collect this value\n\nPLACEHOLDER CONVENTION:\n- {{organization_name}} — legal name of the organization\n- {{ciso_role}} — person responsible for information security\n- {{relevant_role}} — other responsible person/team\n- {{system_name}} — specific system or application\n- {{evidence_record}} — evidence or record to be maintained\n- {{risk_id}} — risk register reference\n- Add domain-specific placeholders as needed following the same pattern\n\nQUESTION FIELD RULES:\n- Must be a complete, natural-language question a consultant would ask the customer\n- Must be specific enough that the answer directly fills the placeholder\n- Examples:\n  - {{organization_name}} → "What is the full legal name of your organization?"\n  - {{ciso_role}} → "Who holds the role of Chief Information Security Officer (or equivalent) in your organization?"\n  - {{review_frequency}} → "How often will this policy be reviewed (e.g. annually, every 6 months)?"\n  - {{incident_response_team}} → "What is the name or composition of your incident response team?"\n\nAUTOMATION HOOKS:\nEach fillable section must include automation metadata:\n- "automation_source": "hr_system" | "asset_inventory" | "risk_register" | "ad_directory" | "manual" | "scan_tool" | "ticketing_system"\n- "auto_fillable": true if this could realistically be auto-populated from a system integration\n- "trigger_event": "employee_onboarding" | "system_change" | "annual_review" | "incident" | "audit"\n\nReturn ONLY valid JSON in this exact structure:\n\n{\n  "summary": {\n    "standard_name": "ISO/IEC 27001:2022",\n    "overview": "2-3 sentence description of what this standard covers and its purpose",\n    "total_clauses": 10,\n    "total_controls": 93,\n    "key_themes": ["Information Security", "Risk Management", "Access Control"],\n    "document_count": 8\n  },\n  "templates": [\n    {\n      "name": "ISMS 01 Information Security Policy",\n      "covered_clauses": ["4.1", "5.1", "5.2"],\n      "covered_controls": ["A.5.1", "A.5.2"],\n      "fixed_sections": [\n        {\n          "id": "purpose",\n          "title": "Purpose",\n          "content": "This Information Security Policy establishes the security objectives and principles for {{organization_name}}. It applies to all employees, contractors, and third parties operating within the organization under the authority of {{ciso_role}}.",\n          "section_type": "policy_statement",\n          "iso_reference": "5.1"\n        }\n      ],\n      "fillable_sections": [\n        {\n          "id": "org_name",\n          "title": "Organization Name",\n          "location": "Purpose section",\n          "type": "text",\n          "semantic_tags": ["organization", "identity"],\n          "placeholder": "{{organization_name}}",\n          "question": "What is the full legal name of your organization?",\n          "is_required": true,\n          "is_mandatory": true,\n          "iso_reference": "4.1",\n          "iso_control_title": "Understanding the organization and its context",\n          "automation_source": "hr_system",\n          "auto_fillable": true,\n          "trigger_event": "annual_review"\n        },\n        {\n          "id": "ciso_responsibility",\n          "title": "Information Security Officer",\n          "location": "Purpose section",\n          "type": "text",\n          "semantic_tags": ["security", "personnel", "leadership"],\n          "placeholder": "{{ciso_role}}",\n          "question": "Who holds the role of Chief Information Security Officer (or equivalent) responsible for information security in your organization?",\n          "is_required": true,\n          "is_mandatory": true,\n          "iso_reference": "A.5.2",\n          "iso_control_title": "Information security roles and responsibilities",\n          "automation_source": "hr_system",\n          "auto_fillable": true,\n          "trigger_event": "annual_review"\n        }\n      ]\n    }\n  ]\n}\n\nISO STANDARD TEXT:\n{{ISO_TEXT}}\n	gemini-2.5-flash	65536	0.20	Generates compliance procedure templates from a full ISO standard PDF. Each fixed_section embeds {{placeholders}} inline; each fillable_section has a question to collect that value.	t	2026-02-23 09:30:40.269287+00
\.


--
-- Data for Name: ai_tasks; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.ai_tasks (id, task_type, related_id, status, progress, current_step, llm_provider_id, llm_provider, llm_model, result, error, cost_usd, tokens_input, tokens_output, duration_seconds, created_at, started_at, completed_at, created_by, template_file_id, trace_id, template_id, iso_standard_id) FROM stdin;
\.


--
-- Data for Name: customer_configuration; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_configuration (id, customer_id, config_type, config_key, config_value, is_template, template_variables, use_ai_phrasing, ai_tone, ai_last_generated_at, ai_generation_prompt, is_active, is_default, created_at, created_by, updated_at, updated_by) FROM stdin;
\.


--
-- Data for Name: customer_documents; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_documents (id, customer_id, plan_id, template_id, template_version, template_name, document_name, document_type, iso_code, status, content, document_version, completion_percentage, mandatory_sections_total, mandatory_sections_completed, storage_path, exported_at, assigned_to, created_by, updated_by, reviewed_by, approved_by, created_at, updated_at, reviewed_at, approved_at, due_date, notes, placeholder_fill_status, last_auto_filled_at) FROM stdin;
\.


--
-- Data for Name: customer_iso_plan_templates; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_iso_plan_templates (id, plan_id, template_id, included, created_at, is_ignored, ignored_at, ignored_by, ignore_reason) FROM stdin;
\.


--
-- Data for Name: customer_iso_plans; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_iso_plans (id, customer_id, iso_standard_id, plan_name, plan_status, template_selection_mode, target_completion_date, started_at, completed_at, created_by, created_at, updated_at, is_ignored, ignored_at, ignored_by, ignore_reason) FROM stdin;
\.


--
-- Data for Name: customer_placeholders; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_placeholders (id, customer_id, plan_id, placeholder_key, display_label, data_type, is_required, status, profile_data_id, template_ids, collected_at, created_at) FROM stdin;
\.


--
-- Data for Name: customer_profile_data; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_profile_data (id, customer_id, field_key, field_value, file_path, file_mime_type, data_type, source, confidence, verified, collected_via_channel_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: customer_tasks; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customer_tasks (id, customer_id, plan_id, document_id, task_type, task_scope, section_id, title, description, status, priority, requires_evidence, evidence_description, evidence_format, evidence_uploaded, evidence_files, assigned_to, due_date, completed_at, completed_by, created_by, created_at, updated_at, notes, auto_generated, is_ignored, ignored_at, ignored_by, ignore_reason, created_manually_by, manual_task_context, template_id, placeholder_key, answer, answer_file_path, answered_at, answered_via, collection_request_id) FROM stdin;
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.customers (id, name, email, contact_person, phone, address, status, metadata, created_by, created_at, updated_at, portal_username, portal_password_hash, contact_email, document_email, storage_type, storage_path, storage_config, portal_enabled, last_portal_login, website, compliance_email, contract_email, description) FROM stdin;
\.


--
-- Data for Name: iso_standards; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.iso_standards (id, code, name, description, requirements_summary, active, display_order, created_at, updated_at, color, ai_metadata) FROM stdin;
\.


--
-- Data for Name: llm_providers; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.llm_providers (id, name, display_name, model, api_key_env, cost_per_1k_input, cost_per_1k_output, max_tokens, enabled, is_default_parser, is_default_reviewer, is_default_chat, created_at, updated_at) FROM stdin;
4ed5b529-05aa-4fed-acfa-46c9e054886a	openai	GPT-4 Turbo	gpt-4-turbo-preview	OPENAI_API_KEY	0.0100	0.0300	4096	f	f	t	f	2026-02-06 22:57:23.866689+00	2026-02-06 22:57:23.866689+00
f84ab3b0-17a0-4d21-9999-472129805588	gemini	Gemini Pro	gemini-pro	GOOGLE_API_KEY	0.0005	0.0015	8192	f	f	f	f	2026-02-06 22:57:23.870847+00	2026-02-06 22:57:23.870847+00
a50e0886-c856-4f41-9c26-a10bc47eb342	claude	Claude Sonnet 4.5	claude-sonnet-4-5-20250929	ANTHROPIC_API_KEY	0.0030	0.0150	8192	t	t	f	t	2026-02-06 22:57:23.845782+00	2026-02-06 22:57:59.158196+00
\.


--
-- Data for Name: task_resolutions; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.task_resolutions (id, task_id, resolution_type, resolution_data, is_final, requires_approval, approved_at, approved_by, quality_score, completeness_score, resolved_by, resolved_at, follow_up_required, follow_up_task_id, notes, attachments) FROM stdin;
\.


--
-- Data for Name: task_templates; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.task_templates (id, template_name, template_description, task_type, task_scope, default_title, default_description, default_priority, default_due_in_days, checklist_items, is_active, is_system_template, usage_count, last_used_at, created_at, created_by) FROM stdin;
\.


--
-- Data for Name: template_files; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.template_files (id, filename, original_filename, file_path, file_size_bytes, file_hash, mime_type, description, version, notes, status, uploaded_by, uploaded_at, updated_at, archived_at, iso_standard_id, file_type, deleted_at, deleted_by) FROM stdin;
\.


--
-- Data for Name: template_iso_mapping; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.template_iso_mapping (template_id, iso_standard_id, created_at, created_by) FROM stdin;
\.


--
-- Data for Name: template_iso_standards; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.template_iso_standards (template_id, iso_standard_id, created_at) FROM stdin;
\.


--
-- Data for Name: template_versions; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.template_versions (id, template_id, version_number, template_structure, change_summary, notes, created_at, created_by, restored_from_version) FROM stdin;
\.


--
-- Data for Name: templates; Type: TABLE DATA; Schema: dna_app; Owner: -
--

COPY dna_app.templates (id, name, description, iso_standard, template_file_id, template_structure, status, version, total_fixed_sections, total_fillable_sections, semantic_tags, ai_task_id, created_at, updated_at, approved_at, approved_by, created_by, version_number, last_edited_at, last_edited_by, restored_from_version) FROM stdin;
\.


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.roles_id_seq', 4, true);


--
-- Name: sessions_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.sessions_id_seq', 190, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.users_id_seq', 1, true);


--
-- Name: customers_id_seq; Type: SEQUENCE SET; Schema: dna_app; Owner: -
--

SELECT pg_catalog.setval('dna_app.customers_id_seq', 8, true);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_session_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_session_id_key UNIQUE (session_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ai_prompts ai_prompts_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_prompts
    ADD CONSTRAINT ai_prompts_pkey PRIMARY KEY (id);


--
-- Name: ai_prompts ai_prompts_prompt_key_key; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_prompts
    ADD CONSTRAINT ai_prompts_prompt_key_key UNIQUE (prompt_key);


--
-- Name: ai_settings; Type: TABLE; Schema: dna_app; Owner: -
-- Stores runtime-editable AI config (provider, model) saved via admin UI
--

CREATE TABLE IF NOT EXISTS dna_app.ai_settings (
    key character varying(100) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT ai_settings_pkey PRIMARY KEY (key)
);

-- Seed defaults
INSERT INTO dna_app.ai_settings (key, value) VALUES
    ('active_provider', 'gemini'),
    ('active_model', 'gemini-2.5-flash')
ON CONFLICT (key) DO NOTHING;


--
-- Name: ai_usage_log; Type: TABLE; Schema: dna_app
-- Tracks every AI call: provider, model, tokens, cost, duration
--

CREATE TABLE IF NOT EXISTS dna_app.ai_usage_log (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id uuid REFERENCES dna_app.ai_tasks(id) ON DELETE SET NULL,
    operation_type varchar(100) NOT NULL,
    provider varchar(50) NOT NULL,
    model varchar(100) NOT NULL,
    tokens_input integer DEFAULT 0,
    tokens_output integer DEFAULT 0,
    tokens_total integer GENERATED ALWAYS AS (tokens_input + tokens_output) STORED,
    cost_usd numeric(10,6) DEFAULT 0,
    duration_ms integer DEFAULT 0,
    status varchar(20) DEFAULT 'success',
    error_message text,
    related_entity_type varchar(50),
    related_entity_id uuid,
    created_by integer,
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_log_task_id ON dna_app.ai_usage_log(task_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_started_at ON dna_app.ai_usage_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_provider ON dna_app.ai_usage_log(provider);


--
-- Name: document_design_configs; Type: TABLE; Schema: dna_app
-- Central design config per language — used for all document previews and generation
--

CREATE TABLE IF NOT EXISTS dna_app.document_design_configs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name varchar(200) NOT NULL,
    language varchar(10) NOT NULL DEFAULT 'en',
    direction varchar(3) NOT NULL DEFAULT 'ltr',
    is_default boolean DEFAULT false,
    config jsonb NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT document_design_configs_lang_default_unique UNIQUE (language, is_default) DEFERRABLE INITIALLY DEFERRED
);

INSERT INTO dna_app.document_design_configs (name, language, direction, is_default, config) VALUES
('Default English', 'en', 'ltr', true, '{
  "document": {"font_family": "Arial, sans-serif", "font_size_base": 11, "margin_cm": 2.5, "page_size": "A4", "line_height": 1.6},
  "colors": {"primary": "#1e3a5f", "secondary": "#374151", "text": "#111827", "muted": "#6b7280", "placeholder_bg": "#fef3c7", "placeholder_border": "#f59e0b", "placeholder_text": "#92400e"},
  "section_types": {
    "title":      {"font_size": 22, "bold": true,  "color": "#1e3a5f", "align": "center", "spacing_before": 0,  "spacing_after": 24, "border_bottom": "3px solid #1e3a5f"},
    "heading":    {"font_size": 14, "bold": true,  "color": "#1e3a5f", "align": "left",   "spacing_before": 20, "spacing_after": 8,  "border_bottom": "1px solid #e5e7eb"},
    "subheading": {"font_size": 12, "bold": true,  "color": "#374151", "align": "left",   "spacing_before": 14, "spacing_after": 6},
    "body":       {"font_size": 11, "bold": false, "color": "#111827", "align": "left",   "spacing_before": 0,  "spacing_after": 10},
    "table":      {"header_bg": "#1e3a5f", "header_color": "#ffffff", "row_alt_bg": "#f9fafb", "border": "1px solid #e5e7eb", "cell_padding": "8px 12px"},
    "list":       {"bullet": "\u2022", "indent_px": 24, "spacing_after": 4},
    "placeholder":{"bg": "#fef3c7", "border": "1px dashed #f59e0b", "color": "#92400e", "border_radius": "3px", "padding": "1px 4px"}
  }
}')
ON CONFLICT DO NOTHING;

INSERT INTO dna_app.document_design_configs (name, language, direction, is_default, config) VALUES
('Default Hebrew', 'he', 'rtl', true, '{
  "document": {"font_family": "\"Noto Sans Hebrew\", Arial, sans-serif", "font_size_base": 12, "margin_cm": 2.5, "page_size": "A4", "line_height": 1.7},
  "colors": {"primary": "#1e3a5f", "secondary": "#374151", "text": "#111827", "muted": "#6b7280", "placeholder_bg": "#fef3c7", "placeholder_border": "#f59e0b", "placeholder_text": "#92400e"},
  "section_types": {
    "title":      {"font_size": 22, "bold": true,  "color": "#1e3a5f", "align": "center", "spacing_before": 0,  "spacing_after": 24, "border_bottom": "3px solid #1e3a5f"},
    "heading":    {"font_size": 14, "bold": true,  "color": "#1e3a5f", "align": "right",  "spacing_before": 20, "spacing_after": 8,  "border_bottom": "1px solid #e5e7eb"},
    "subheading": {"font_size": 12, "bold": true,  "color": "#374151", "align": "right",  "spacing_before": 14, "spacing_after": 6},
    "body":       {"font_size": 12, "bold": false, "color": "#111827", "align": "right",  "spacing_before": 0,  "spacing_after": 10},
    "table":      {"header_bg": "#1e3a5f", "header_color": "#ffffff", "row_alt_bg": "#f9fafb", "border": "1px solid #e5e7eb", "cell_padding": "8px 12px"},
    "list":       {"bullet": "\u2022", "indent_px": 24, "spacing_after": 4},
    "placeholder":{"bg": "#fef3c7", "border": "1px dashed #f59e0b", "color": "#92400e", "border_radius": "3px", "padding": "1px 4px"}
  }
}')
ON CONFLICT DO NOTHING;


--
-- Name: ai_tasks ai_tasks_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_pkey PRIMARY KEY (id);


--
-- Name: customer_configuration customer_configuration_customer_id_config_type_config_key_key; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_configuration
    ADD CONSTRAINT customer_configuration_customer_id_config_type_config_key_key UNIQUE (customer_id, config_type, config_key);


--
-- Name: customer_configuration customer_configuration_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_configuration
    ADD CONSTRAINT customer_configuration_pkey PRIMARY KEY (id);


--
-- Name: customer_documents customer_documents_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_pkey PRIMARY KEY (id);


--
-- Name: customer_iso_plan_templates customer_iso_plan_templates_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plan_templates
    ADD CONSTRAINT customer_iso_plan_templates_pkey PRIMARY KEY (id);


--
-- Name: customer_iso_plans customer_iso_plans_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT customer_iso_plans_pkey PRIMARY KEY (id);


--
-- Name: customer_placeholders customer_placeholders_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_placeholders
    ADD CONSTRAINT customer_placeholders_pkey PRIMARY KEY (id);


--
-- Name: customer_profile_data customer_profile_data_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_profile_data
    ADD CONSTRAINT customer_profile_data_pkey PRIMARY KEY (id);


--
-- Name: customer_tasks customer_tasks_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: customers customers_portal_username_key; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customers
    ADD CONSTRAINT customers_portal_username_key UNIQUE (portal_username);


--
-- Name: iso_standards iso_standards_code_key; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.iso_standards
    ADD CONSTRAINT iso_standards_code_key UNIQUE (code);


--
-- Name: iso_standards iso_standards_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.iso_standards
    ADD CONSTRAINT iso_standards_pkey PRIMARY KEY (id);


--
-- Name: llm_providers llm_providers_name_key; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.llm_providers
    ADD CONSTRAINT llm_providers_name_key UNIQUE (name);


--
-- Name: llm_providers llm_providers_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.llm_providers
    ADD CONSTRAINT llm_providers_pkey PRIMARY KEY (id);


--
-- Name: task_resolutions task_resolutions_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_resolutions
    ADD CONSTRAINT task_resolutions_pkey PRIMARY KEY (id);


--
-- Name: task_templates task_templates_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_templates
    ADD CONSTRAINT task_templates_pkey PRIMARY KEY (id);


--
-- Name: template_files template_files_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_files
    ADD CONSTRAINT template_files_pkey PRIMARY KEY (id);


--
-- Name: template_iso_mapping template_iso_mapping_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_mapping
    ADD CONSTRAINT template_iso_mapping_pkey PRIMARY KEY (template_id, iso_standard_id);


--
-- Name: template_iso_standards template_iso_standards_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_standards
    ADD CONSTRAINT template_iso_standards_pkey PRIMARY KEY (template_id, iso_standard_id);


--
-- Name: template_versions template_versions_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_versions
    ADD CONSTRAINT template_versions_pkey PRIMARY KEY (id);


--
-- Name: templates templates_pkey; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_pkey PRIMARY KEY (id);


--
-- Name: customer_iso_plans unique_active_iso_per_customer; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT unique_active_iso_per_customer UNIQUE (customer_id, iso_standard_id);


--
-- Name: customer_profile_data unique_customer_field; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_profile_data
    ADD CONSTRAINT unique_customer_field UNIQUE (customer_id, field_key);


--
-- Name: customer_placeholders unique_customer_plan_placeholder; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_placeholders
    ADD CONSTRAINT unique_customer_plan_placeholder UNIQUE (customer_id, plan_id, placeholder_key);


--
-- Name: template_files unique_filename_version; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_files
    ADD CONSTRAINT unique_filename_version UNIQUE (filename, version);


--
-- Name: customer_iso_plan_templates unique_plan_template; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plan_templates
    ADD CONSTRAINT unique_plan_template UNIQUE (plan_id, template_id);


--
-- Name: template_versions unique_template_version; Type: CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_versions
    ADD CONSTRAINT unique_template_version UNIQUE (template_id, version_number);


--
-- Name: idx_sessions_expires_at; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_sessions_expires_at ON auth.sessions USING btree (expires_at);


--
-- Name: idx_sessions_session_id; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_sessions_session_id ON auth.sessions USING btree (session_id);


--
-- Name: idx_sessions_user_id; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_sessions_user_id ON auth.sessions USING btree (user_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_email ON auth.users USING btree (email);


--
-- Name: idx_users_is_active; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_is_active ON auth.users USING btree (is_active);


--
-- Name: idx_users_role; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_role ON auth.users USING btree (role);


--
-- Name: idx_users_role_id; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_role_id ON auth.users USING btree (role_id);


--
-- Name: idx_ai_tasks_created_at; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_created_at ON dna_app.ai_tasks USING btree (created_at DESC);


--
-- Name: idx_ai_tasks_created_by; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_created_by ON dna_app.ai_tasks USING btree (created_by);


--
-- Name: idx_ai_tasks_provider; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_provider ON dna_app.ai_tasks USING btree (llm_provider_id);


--
-- Name: idx_ai_tasks_related; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_related ON dna_app.ai_tasks USING btree (related_id);


--
-- Name: idx_ai_tasks_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_status ON dna_app.ai_tasks USING btree (status);


--
-- Name: idx_ai_tasks_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_template ON dna_app.ai_tasks USING btree (template_id);


--
-- Name: idx_ai_tasks_template_file; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_template_file ON dna_app.ai_tasks USING btree (template_file_id);


--
-- Name: idx_ai_tasks_trace_id; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_trace_id ON dna_app.ai_tasks USING btree (trace_id);


--
-- Name: idx_ai_tasks_type; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_ai_tasks_type ON dna_app.ai_tasks USING btree (task_type);


--
-- Name: idx_customer_config_active; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_config_active ON dna_app.customer_configuration USING btree (is_active);


--
-- Name: idx_customer_config_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_config_customer ON dna_app.customer_configuration USING btree (customer_id);


--
-- Name: idx_customer_config_type; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_config_type ON dna_app.customer_configuration USING btree (config_type);


--
-- Name: idx_customer_documents_assigned; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_assigned ON dna_app.customer_documents USING btree (assigned_to);


--
-- Name: idx_customer_documents_completion; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_completion ON dna_app.customer_documents USING btree (completion_percentage);


--
-- Name: idx_customer_documents_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_customer ON dna_app.customer_documents USING btree (customer_id);


--
-- Name: idx_customer_documents_plan; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_plan ON dna_app.customer_documents USING btree (plan_id);


--
-- Name: idx_customer_documents_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_status ON dna_app.customer_documents USING btree (status);


--
-- Name: idx_customer_documents_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_documents_template ON dna_app.customer_documents USING btree (template_id);


--
-- Name: idx_customer_iso_plans_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_iso_plans_customer ON dna_app.customer_iso_plans USING btree (customer_id);


--
-- Name: idx_customer_iso_plans_iso; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_iso_plans_iso ON dna_app.customer_iso_plans USING btree (iso_standard_id);


--
-- Name: idx_customer_iso_plans_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_iso_plans_status ON dna_app.customer_iso_plans USING btree (plan_status);


--
-- Name: idx_customer_tasks_answered; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_answered ON dna_app.customer_tasks USING btree (answered_at) WHERE (answered_at IS NOT NULL);


--
-- Name: idx_customer_tasks_assigned; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_assigned ON dna_app.customer_tasks USING btree (assigned_to);


--
-- Name: idx_customer_tasks_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_customer ON dna_app.customer_tasks USING btree (customer_id);


--
-- Name: idx_customer_tasks_document; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_document ON dna_app.customer_tasks USING btree (document_id);


--
-- Name: idx_customer_tasks_due; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_due ON dna_app.customer_tasks USING btree (due_date);


--
-- Name: idx_customer_tasks_evidence; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_evidence ON dna_app.customer_tasks USING btree (requires_evidence, evidence_uploaded);


--
-- Name: idx_customer_tasks_placeholder; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_placeholder ON dna_app.customer_tasks USING btree (placeholder_key);


--
-- Name: idx_customer_tasks_plan; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_plan ON dna_app.customer_tasks USING btree (plan_id);


--
-- Name: idx_customer_tasks_scope; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_scope ON dna_app.customer_tasks USING btree (task_scope);


--
-- Name: idx_customer_tasks_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_status ON dna_app.customer_tasks USING btree (status);


--
-- Name: idx_customer_tasks_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customer_tasks_template ON dna_app.customer_tasks USING btree (template_id);


--
-- Name: idx_customers_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_customers_status ON dna_app.customers USING btree (status);


--
-- Name: idx_iso_standards_active; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_iso_standards_active ON dna_app.iso_standards USING btree (active);


--
-- Name: idx_iso_standards_code; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_iso_standards_code ON dna_app.iso_standards USING btree (code);


--
-- Name: idx_iso_standards_order; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_iso_standards_order ON dna_app.iso_standards USING btree (display_order);


--
-- Name: idx_llm_providers_default_parser; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_llm_providers_default_parser ON dna_app.llm_providers USING btree (is_default_parser) WHERE (is_default_parser = true);


--
-- Name: idx_llm_providers_enabled; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_llm_providers_enabled ON dna_app.llm_providers USING btree (enabled);


--
-- Name: idx_llm_providers_name; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_llm_providers_name ON dna_app.llm_providers USING btree (name);


--
-- Name: idx_placeholders_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_placeholders_customer ON dna_app.customer_placeholders USING btree (customer_id);


--
-- Name: idx_placeholders_key; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_placeholders_key ON dna_app.customer_placeholders USING btree (placeholder_key);


--
-- Name: idx_placeholders_plan; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_placeholders_plan ON dna_app.customer_placeholders USING btree (plan_id);


--
-- Name: idx_placeholders_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_placeholders_status ON dna_app.customer_placeholders USING btree (status);


--
-- Name: idx_plan_templates_plan; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_plan_templates_plan ON dna_app.customer_iso_plan_templates USING btree (plan_id);


--
-- Name: idx_plan_templates_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_plan_templates_template ON dna_app.customer_iso_plan_templates USING btree (template_id);


--
-- Name: idx_profile_data_customer; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_profile_data_customer ON dna_app.customer_profile_data USING btree (customer_id);


--
-- Name: idx_profile_data_key; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_profile_data_key ON dna_app.customer_profile_data USING btree (field_key);


--
-- Name: idx_profile_data_verified; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_profile_data_verified ON dna_app.customer_profile_data USING btree (verified);


--
-- Name: idx_task_resolution_requires_approval; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_resolution_requires_approval ON dna_app.task_resolutions USING btree (requires_approval) WHERE (requires_approval = true);


--
-- Name: idx_task_resolution_task; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_resolution_task ON dna_app.task_resolutions USING btree (task_id);


--
-- Name: idx_task_resolution_type; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_resolution_type ON dna_app.task_resolutions USING btree (resolution_type);


--
-- Name: idx_task_template_active; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_template_active ON dna_app.task_templates USING btree (is_active);


--
-- Name: idx_task_template_scope; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_template_scope ON dna_app.task_templates USING btree (task_scope);


--
-- Name: idx_task_template_type; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_task_template_type ON dna_app.task_templates USING btree (task_type);


--
-- Name: idx_template_files_deleted; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_deleted ON dna_app.template_files USING btree (deleted_at) WHERE (deleted_at IS NOT NULL);


--
-- Name: idx_template_files_filename; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_filename ON dna_app.template_files USING btree (filename);


--
-- Name: idx_template_files_hash; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_hash ON dna_app.template_files USING btree (file_hash);


--
-- Name: idx_template_files_iso_standard; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_iso_standard ON dna_app.template_files USING btree (iso_standard_id);


--
-- Name: idx_template_files_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_status ON dna_app.template_files USING btree (status);


--
-- Name: idx_template_files_type; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_type ON dna_app.template_files USING btree (file_type);


--
-- Name: idx_template_files_uploaded; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_uploaded ON dna_app.template_files USING btree (uploaded_at DESC);


--
-- Name: idx_template_files_uploader; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_files_uploader ON dna_app.template_files USING btree (uploaded_by);


--
-- Name: idx_template_iso_standard; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_iso_standard ON dna_app.template_iso_mapping USING btree (iso_standard_id);


--
-- Name: idx_template_iso_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_iso_template ON dna_app.template_iso_mapping USING btree (template_id);


--
-- Name: idx_template_versions_created; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_versions_created ON dna_app.template_versions USING btree (created_at DESC);


--
-- Name: idx_template_versions_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_template_versions_template ON dna_app.template_versions USING btree (template_id, version_number DESC);


--
-- Name: idx_templates_created; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_created ON dna_app.templates USING btree (created_at DESC);


--
-- Name: idx_templates_file; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_file ON dna_app.templates USING btree (template_file_id);


--
-- Name: idx_templates_iso; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_iso ON dna_app.templates USING btree (iso_standard);


--
-- Name: idx_templates_last_edited; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_last_edited ON dna_app.templates USING btree (last_edited_at DESC);


--
-- Name: idx_templates_name; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_name ON dna_app.templates USING btree (name);


--
-- Name: idx_templates_status; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_status ON dna_app.templates USING btree (status);


--
-- Name: idx_templates_tags; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_tags ON dna_app.templates USING gin (semantic_tags);


--
-- Name: idx_templates_task; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE INDEX idx_templates_task ON dna_app.templates USING btree (ai_task_id);


--
-- Name: uq_customer_documents_plan_template; Type: INDEX; Schema: dna_app; Owner: -
--

CREATE UNIQUE INDEX uq_customer_documents_plan_template ON dna_app.customer_documents USING btree (customer_id, plan_id, template_id);


--
-- Name: v_reference_documents _RETURN; Type: RULE; Schema: dna_app; Owner: -
--

CREATE OR REPLACE VIEW dna_app.v_reference_documents AS
 SELECT tf.id,
    tf.filename,
    tf.original_filename,
    tf.file_path,
    tf.file_size_bytes,
    tf.file_hash,
    tf.mime_type,
    tf.description,
    tf.version,
    tf.notes,
    tf.status,
    tf.uploaded_by,
    tf.uploaded_at,
    tf.updated_at,
    tf.archived_at,
    tf.iso_standard_id,
    tf.file_type,
    tf.deleted_at,
    tf.deleted_by,
    iso.code AS iso_standard_code,
    iso.name AS iso_standard_name,
    u.email AS uploaded_by_email,
    count(DISTINCT t.id) AS template_count,
    count(DISTINCT at.id) AS analysis_count
   FROM ((((dna_app.template_files tf
     LEFT JOIN dna_app.iso_standards iso ON ((tf.iso_standard_id = iso.id)))
     LEFT JOIN auth.users u ON ((tf.uploaded_by = u.id)))
     LEFT JOIN dna_app.templates t ON ((t.template_file_id = tf.id)))
     LEFT JOIN dna_app.ai_tasks at ON ((at.template_file_id = tf.id)))
  WHERE (((tf.file_type)::text = 'reference'::text) AND (tf.deleted_at IS NULL))
  GROUP BY tf.id, iso.id, u.email;


--
-- Name: v_template_files_with_details _RETURN; Type: RULE; Schema: dna_app; Owner: -
--

CREATE OR REPLACE VIEW dna_app.v_template_files_with_details AS
 SELECT tf.id,
    tf.filename,
    tf.original_filename,
    tf.file_path,
    tf.file_size_bytes,
    tf.description,
    tf.status,
    tf.uploaded_at,
    u.email AS uploaded_by_email,
    count(DISTINCT t.id) AS built_templates_count
   FROM ((dna_app.template_files tf
     LEFT JOIN auth.users u ON ((tf.uploaded_by = u.id)))
     LEFT JOIN dna_app.templates t ON ((tf.id = t.template_file_id)))
  WHERE ((tf.status)::text = 'uploaded'::text)
  GROUP BY tf.id, u.email
  ORDER BY tf.uploaded_at DESC;


--
-- Name: v_templates_with_versions _RETURN; Type: RULE; Schema: dna_app; Owner: -
--

CREATE OR REPLACE VIEW dna_app.v_templates_with_versions AS
 SELECT t.id,
    t.name,
    t.description,
    t.iso_standard,
    t.template_file_id,
    t.template_structure,
    t.status,
    t.version_number,
    t.total_fixed_sections,
    t.total_fillable_sections,
    t.semantic_tags,
    t.created_at,
    t.updated_at,
    t.approved_at,
    t.last_edited_at,
    t.last_edited_by,
    u_edited.email AS last_edited_by_email,
    count(DISTINCT tv.id) AS total_versions
   FROM ((dna_app.templates t
     LEFT JOIN auth.users u_edited ON ((t.last_edited_by = u_edited.id)))
     LEFT JOIN dna_app.template_versions tv ON ((t.id = tv.template_id)))
  GROUP BY t.id, u_edited.email;


--
-- Name: roles trigger_roles_updated_at; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER trigger_roles_updated_at BEFORE UPDATE ON auth.roles FOR EACH ROW EXECUTE FUNCTION auth.update_roles_updated_at();


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: auth; Owner: -
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON auth.users FOR EACH ROW EXECUTE FUNCTION auth.update_updated_at_column();


--
-- Name: customer_placeholders trg_placeholder_to_document; Type: TRIGGER; Schema: dna_app; Owner: -
--

CREATE TRIGGER trg_placeholder_to_document AFTER UPDATE OF status ON dna_app.customer_placeholders FOR EACH ROW WHEN (((old.status)::text IS DISTINCT FROM (new.status)::text)) EXECUTE FUNCTION dna_app.sync_document_from_placeholder();


--
-- Name: customer_placeholders trg_placeholder_to_task; Type: TRIGGER; Schema: dna_app; Owner: -
--

CREATE TRIGGER trg_placeholder_to_task AFTER UPDATE OF status ON dna_app.customer_placeholders FOR EACH ROW WHEN (((old.status)::text IS DISTINCT FROM (new.status)::text)) EXECUTE FUNCTION dna_app.sync_task_from_placeholder();


--
-- Name: customer_tasks trg_task_to_placeholder; Type: TRIGGER; Schema: dna_app; Owner: -
--

CREATE TRIGGER trg_task_to_placeholder AFTER UPDATE OF status ON dna_app.customer_tasks FOR EACH ROW WHEN (((old.status)::text IS DISTINCT FROM (new.status)::text)) EXECUTE FUNCTION dna_app.sync_placeholder_from_task();


--
-- Name: customer_configuration trigger_update_customer_config_updated_at; Type: TRIGGER; Schema: dna_app; Owner: -
--

CREATE TRIGGER trigger_update_customer_config_updated_at BEFORE UPDATE ON dna_app.customer_configuration FOR EACH ROW EXECUTE FUNCTION dna_app.update_customer_config_updated_at();


--
-- Name: customers update_customers_updated_at; Type: TRIGGER; Schema: dna_app; Owner: -
--

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON dna_app.customers FOR EACH ROW EXECUTE FUNCTION auth.update_updated_at_column();


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: users users_role_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_role_id_fkey FOREIGN KEY (role_id) REFERENCES auth.roles(id);


--
-- Name: ai_tasks ai_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: ai_tasks ai_tasks_iso_standard_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_iso_standard_id_fkey FOREIGN KEY (iso_standard_id) REFERENCES dna_app.iso_standards(id) ON DELETE SET NULL;


--
-- Name: ai_tasks ai_tasks_llm_provider_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_llm_provider_id_fkey FOREIGN KEY (llm_provider_id) REFERENCES dna_app.llm_providers(id);


--
-- Name: ai_tasks ai_tasks_template_file_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_template_file_id_fkey FOREIGN KEY (template_file_id) REFERENCES dna_app.template_files(id) ON DELETE CASCADE;


--
-- Name: ai_tasks ai_tasks_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.ai_tasks
    ADD CONSTRAINT ai_tasks_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE SET NULL;


--
-- Name: customer_configuration customer_configuration_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_configuration
    ADD CONSTRAINT customer_configuration_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: customer_configuration customer_configuration_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_configuration
    ADD CONSTRAINT customer_configuration_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_configuration customer_configuration_updated_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_configuration
    ADD CONSTRAINT customer_configuration_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES auth.users(id);


--
-- Name: customer_documents customer_documents_approved_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES auth.users(id);


--
-- Name: customer_documents customer_documents_assigned_to_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES auth.users(id);


--
-- Name: customer_documents customer_documents_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: customer_documents customer_documents_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_documents customer_documents_plan_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE;


--
-- Name: customer_documents customer_documents_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES auth.users(id);


--
-- Name: customer_documents customer_documents_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE RESTRICT;


--
-- Name: customer_documents customer_documents_updated_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_documents
    ADD CONSTRAINT customer_documents_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES auth.users(id);


--
-- Name: customer_iso_plan_templates customer_iso_plan_templates_ignored_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plan_templates
    ADD CONSTRAINT customer_iso_plan_templates_ignored_by_fkey FOREIGN KEY (ignored_by) REFERENCES auth.users(id);


--
-- Name: customer_iso_plan_templates customer_iso_plan_templates_plan_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plan_templates
    ADD CONSTRAINT customer_iso_plan_templates_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE;


--
-- Name: customer_iso_plan_templates customer_iso_plan_templates_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plan_templates
    ADD CONSTRAINT customer_iso_plan_templates_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE RESTRICT;


--
-- Name: customer_iso_plans customer_iso_plans_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT customer_iso_plans_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: customer_iso_plans customer_iso_plans_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT customer_iso_plans_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_iso_plans customer_iso_plans_ignored_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT customer_iso_plans_ignored_by_fkey FOREIGN KEY (ignored_by) REFERENCES auth.users(id);


--
-- Name: customer_iso_plans customer_iso_plans_iso_standard_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_iso_plans
    ADD CONSTRAINT customer_iso_plans_iso_standard_id_fkey FOREIGN KEY (iso_standard_id) REFERENCES dna_app.iso_standards(id) ON DELETE RESTRICT;


--
-- Name: customer_placeholders customer_placeholders_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_placeholders
    ADD CONSTRAINT customer_placeholders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_placeholders customer_placeholders_plan_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_placeholders
    ADD CONSTRAINT customer_placeholders_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE;


--
-- Name: customer_placeholders customer_placeholders_profile_data_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_placeholders
    ADD CONSTRAINT customer_placeholders_profile_data_id_fkey FOREIGN KEY (profile_data_id) REFERENCES dna_app.customer_profile_data(id) ON DELETE SET NULL;


--
-- Name: customer_profile_data customer_profile_data_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_profile_data
    ADD CONSTRAINT customer_profile_data_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_tasks customer_tasks_assigned_to_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES auth.users(id);


--
-- Name: customer_tasks customer_tasks_completed_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES auth.users(id);


--
-- Name: customer_tasks customer_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: customer_tasks customer_tasks_created_manually_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_created_manually_by_fkey FOREIGN KEY (created_manually_by) REFERENCES auth.users(id);


--
-- Name: customer_tasks customer_tasks_customer_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES dna_app.customers(id) ON DELETE CASCADE;


--
-- Name: customer_tasks customer_tasks_document_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_document_id_fkey FOREIGN KEY (document_id) REFERENCES dna_app.customer_documents(id) ON DELETE CASCADE;


--
-- Name: customer_tasks customer_tasks_ignored_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_ignored_by_fkey FOREIGN KEY (ignored_by) REFERENCES auth.users(id);


--
-- Name: customer_tasks customer_tasks_plan_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES dna_app.customer_iso_plans(id) ON DELETE CASCADE;


--
-- Name: customer_tasks customer_tasks_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customer_tasks
    ADD CONSTRAINT customer_tasks_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE CASCADE;


--
-- Name: customers customers_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.customers
    ADD CONSTRAINT customers_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: task_resolutions task_resolutions_approved_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_resolutions
    ADD CONSTRAINT task_resolutions_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES auth.users(id);


--
-- Name: task_resolutions task_resolutions_follow_up_task_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_resolutions
    ADD CONSTRAINT task_resolutions_follow_up_task_id_fkey FOREIGN KEY (follow_up_task_id) REFERENCES dna_app.customer_tasks(id);


--
-- Name: task_resolutions task_resolutions_resolved_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_resolutions
    ADD CONSTRAINT task_resolutions_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES auth.users(id);


--
-- Name: task_resolutions task_resolutions_task_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_resolutions
    ADD CONSTRAINT task_resolutions_task_id_fkey FOREIGN KEY (task_id) REFERENCES dna_app.customer_tasks(id) ON DELETE CASCADE;


--
-- Name: task_templates task_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.task_templates
    ADD CONSTRAINT task_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: template_files template_files_deleted_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_files
    ADD CONSTRAINT template_files_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES auth.users(id);


--
-- Name: template_files template_files_iso_standard_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_files
    ADD CONSTRAINT template_files_iso_standard_id_fkey FOREIGN KEY (iso_standard_id) REFERENCES dna_app.iso_standards(id) ON DELETE SET NULL;


--
-- Name: template_files template_files_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_files
    ADD CONSTRAINT template_files_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES auth.users(id);


--
-- Name: template_iso_mapping template_iso_mapping_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_mapping
    ADD CONSTRAINT template_iso_mapping_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: template_iso_mapping template_iso_mapping_iso_standard_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_mapping
    ADD CONSTRAINT template_iso_mapping_iso_standard_id_fkey FOREIGN KEY (iso_standard_id) REFERENCES dna_app.iso_standards(id) ON DELETE CASCADE;


--
-- Name: template_iso_mapping template_iso_mapping_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_mapping
    ADD CONSTRAINT template_iso_mapping_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE CASCADE;


--
-- Name: template_iso_standards template_iso_standards_iso_standard_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_standards
    ADD CONSTRAINT template_iso_standards_iso_standard_id_fkey FOREIGN KEY (iso_standard_id) REFERENCES dna_app.iso_standards(id) ON DELETE CASCADE;


--
-- Name: template_iso_standards template_iso_standards_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_iso_standards
    ADD CONSTRAINT template_iso_standards_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE CASCADE;


--
-- Name: template_versions template_versions_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_versions
    ADD CONSTRAINT template_versions_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: template_versions template_versions_template_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.template_versions
    ADD CONSTRAINT template_versions_template_id_fkey FOREIGN KEY (template_id) REFERENCES dna_app.templates(id) ON DELETE CASCADE;


--
-- Name: templates templates_ai_task_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_ai_task_id_fkey FOREIGN KEY (ai_task_id) REFERENCES dna_app.ai_tasks(id) ON DELETE SET NULL;


--
-- Name: templates templates_approved_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES auth.users(id);


--
-- Name: templates templates_created_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);


--
-- Name: templates templates_last_edited_by_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_last_edited_by_fkey FOREIGN KEY (last_edited_by) REFERENCES auth.users(id);


--
-- Name: templates templates_template_file_id_fkey; Type: FK CONSTRAINT; Schema: dna_app; Owner: -
--

ALTER TABLE ONLY dna_app.templates
    ADD CONSTRAINT templates_template_file_id_fkey FOREIGN KEY (template_file_id) REFERENCES dna_app.template_files(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict jVq5Ab84mOARzZdISWGMUTuviofMOBcnjHeIcNDjdW01ddZNpRtzTvmBcsBPm7L

