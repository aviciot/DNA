"use client";

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2, Mail, Key, Shield, CheckCircle2, ArrowRight, ArrowLeft,
  X, Eye, EyeOff, RefreshCw, Copy, Check, Plus, Trash2, Calendar,
  FileText, CheckSquare, Sparkles,
} from "lucide-react";
import api from "@/lib/api";

const STEPS = [
  { id: 1, name: "Company Info", icon: Building2 },
  { id: 2, name: "Contact", icon: Mail },
  { id: 3, name: "Portal", icon: Key },
  { id: 4, name: "ISOs", icon: Shield },
  { id: 5, name: "Review", icon: CheckCircle2 },
];

interface WizardStep {
  onNext: () => void;
  onBack: () => void;
  onSkip?: () => void;
  data: any;
  updateData: (data: any) => void;
}

interface CustomerCreationWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (customer: any) => void;
}

const EMPTY_DATA = {
  companyName: "", website: "", contactPerson: "", phone: "", address: "", description: "",
  email: "", contactEmail: "", documentEmail: "", complianceEmail: "", contractEmail: "",
  storageType: "local",
  portalEnabled: false, portalUsername: "", portalPassword: "",
  isoAssignments: [] as any[],
  confirmed: false,
};

export default function CustomerCreationWizard({ isOpen, onClose, onSuccess }: CustomerCreationWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [wizardData, setWizardData] = useState(EMPTY_DATA);

  const updateWizardData = useCallback((data: Partial<typeof EMPTY_DATA>) => {
    setWizardData((prev) => ({ ...prev, ...data }));
  }, []);

  const handleNext = useCallback(() => {
    if (currentStep < STEPS.length) setCurrentStep((p) => p + 1);
  }, [currentStep]);

  const handleBack = useCallback(() => {
    if (currentStep > 1) setCurrentStep((p) => p - 1);
  }, [currentStep]);

  const handleSkip = useCallback(() => {
    if (currentStep < STEPS.length) setCurrentStep((p) => p + 1);
  }, [currentStep]);

  const handleClose = useCallback(() => {
    if (confirm("Are you sure you want to cancel customer creation?")) {
      onClose();
      setCurrentStep(1);
      setWizardData(EMPTY_DATA);
    }
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden"
      >
        <div className="relative bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 px-8 py-6">
          <button onClick={handleClose} className="absolute top-6 right-6 text-white/80 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
          <h2 className="text-3xl font-bold text-white mb-2">Create New Customer</h2>
          <p className="text-blue-100">Set up a new customer with ISO certification management</p>
        </div>

        <div className="px-8 py-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <motion.div
                    initial={false}
                    animate={{
                      scale: currentStep === step.id ? 1.1 : 1,
                      backgroundColor: currentStep >= step.id ? "rgb(37, 99, 235)" : "rgb(229, 231, 235)",
                    }}
                    className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                      currentStep >= step.id
                        ? "bg-blue-600 text-white shadow-lg shadow-blue-500/50"
                        : "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400"
                    }`}
                  >
                    {currentStep > step.id ? <CheckCircle2 className="w-6 h-6" /> : <step.icon className="w-6 h-6" />}
                  </motion.div>
                  <span className={`mt-2 text-sm font-medium ${currentStep >= step.id ? "text-blue-600 dark:text-blue-400" : "text-gray-500 dark:text-gray-400"}`}>
                    {step.name}
                  </span>
                </div>
                {index < STEPS.length - 1 && (
                  <motion.div
                    initial={false}
                    animate={{ backgroundColor: currentStep > step.id ? "rgb(37, 99, 235)" : "rgb(229, 231, 235)" }}
                    className="h-1 flex-1 mx-2 rounded-full"
                    style={{ marginTop: "-2.5rem" }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="px-8 py-6 overflow-y-auto" style={{ maxHeight: "calc(90vh - 280px)" }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
            >
              {currentStep === 1 && <CompanyInfoStep onNext={handleNext} onBack={handleBack} data={wizardData} updateData={updateWizardData} />}
              {currentStep === 2 && <ContactStep onNext={handleNext} onBack={handleBack} data={wizardData} updateData={updateWizardData} />}
              {currentStep === 3 && <PortalStep onNext={handleNext} onBack={handleBack} onSkip={handleSkip} data={wizardData} updateData={updateWizardData} />}
              {currentStep === 4 && <ISOAssignmentStep onNext={handleNext} onBack={handleBack} onSkip={handleSkip} data={wizardData} updateData={updateWizardData} />}
              {currentStep === 5 && <ReviewStep onBack={handleBack} data={wizardData} onSuccess={onSuccess} onClose={onClose} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}

const inp = "w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400";

function CompanyInfoStep({ onNext, data, updateData }: WizardStep) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleNext = () => {
    if (!data.companyName?.trim()) { setErrors({ companyName: "Company name is required" }); return; }
    setErrors({});
    onNext();
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Company Information</h3>
        <p className="text-gray-600 dark:text-gray-400">Tell us about the company you're onboarding</p>
      </div>
      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Company Name <span className="text-red-500">*</span></label>
          <input type="text" value={data.companyName} onChange={(e) => updateData({ companyName: e.target.value })} placeholder="Acme Corporation"
            className={`${inp} ${errors.companyName ? "border-red-500" : ""}`} />
          {errors.companyName && <p className="mt-1 text-sm text-red-500">{errors.companyName}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Website</label>
          <input type="url" value={data.website} onChange={(e) => updateData({ website: e.target.value })} placeholder="https://www.acmecorp.com" className={inp} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Contact Person</label>
            <input type="text" value={data.contactPerson} onChange={(e) => updateData({ contactPerson: e.target.value })} placeholder="John Smith" className={inp} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Phone</label>
            <input type="tel" value={data.phone} onChange={(e) => updateData({ phone: e.target.value })} placeholder="+1-555-0123" className={inp} />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Address</label>
          <textarea value={data.address} onChange={(e) => updateData({ address: e.target.value })} placeholder="123 Main Street, New York, NY 10001" rows={2}
            className={`${inp} resize-none`} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description / Notes</label>
          <textarea value={data.description} onChange={(e) => updateData({ description: e.target.value })} placeholder="Optional notes about this customer" rows={2}
            className={`${inp} resize-none`} />
        </div>
      </div>
      <div className="flex justify-end mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button onClick={handleNext} className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md flex items-center space-x-2 font-medium">
          <span>Next</span><ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

function ContactStep({ onNext, onBack, data, updateData }: WizardStep) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleNext = () => {
    if (!data.email?.trim()) { setErrors({ email: "Primary email is required" }); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) { setErrors({ email: "Invalid email format" }); return; }
    setErrors({});
    if (!data.contactEmail) updateData({ contactEmail: data.email });
    if (!data.documentEmail) updateData({ documentEmail: data.email });
    onNext();
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Contact & Communication</h3>
        <p className="text-gray-600 dark:text-gray-400">How should we communicate with this customer?</p>
      </div>
      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Primary Email <span className="text-red-500">*</span></label>
          <input type="email" value={data.email} onChange={(e) => updateData({ email: e.target.value })} placeholder="john@acmecorp.com"
            className={`${inp} ${errors.email ? "border-red-500" : ""}`} />
          {errors.email && <p className="mt-1 text-sm text-red-500">{errors.email}</p>}
          <p className="mt-1 text-xs text-gray-500">Used for login and notifications</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Contact Email</label>
            <input type="email" value={data.contactEmail} onChange={(e) => updateData({ contactEmail: e.target.value })} placeholder="Defaults to primary" className={inp} />
            <p className="mt-1 text-xs text-gray-500">For general communication</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Document Email</label>
            <input type="email" value={data.documentEmail} onChange={(e) => updateData({ documentEmail: e.target.value })} placeholder="compliance@acmecorp.com" className={inp} />
            <p className="mt-1 text-xs text-gray-500">For sending/receiving documents</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Compliance Email</label>
            <input type="email" value={data.complianceEmail} onChange={(e) => updateData({ complianceEmail: e.target.value })} placeholder="evidence@acmecorp.com" className={inp} />
            <p className="mt-1 text-xs text-gray-500">For evidence/document automation</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Contract Email</label>
            <input type="email" value={data.contractEmail} onChange={(e) => updateData({ contractEmail: e.target.value })} placeholder="legal@acmecorp.com" className={inp} />
            <p className="mt-1 text-xs text-gray-500">For CISO/Legal</p>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Storage Type</label>
          <label className="flex items-center p-4 rounded-lg border-2 border-blue-500 bg-blue-50 dark:bg-blue-900/20 cursor-pointer">
            <input type="radio" name="storage" value="local" checked={data.storageType === "local"} onChange={(e) => updateData({ storageType: e.target.value })} className="w-4 h-4 text-blue-600" />
            <div className="ml-3 flex-1">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900 dark:text-white">Local Storage</span>
                <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded-full">Recommended</span>
              </div>
              <span className="text-sm text-gray-600 dark:text-gray-400">Files stored on server filesystem</span>
            </div>
          </label>
        </div>
      </div>
      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button onClick={onBack} className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center space-x-2">
          <ArrowLeft className="w-5 h-5" /><span>Back</span>
        </button>
        <button onClick={handleNext} className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md flex items-center space-x-2 font-medium">
          <span>Next</span><ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

function PortalStep({ onNext, onBack, onSkip, data, updateData }: WizardStep) {
  const [showPassword, setShowPassword] = useState(false);
  const [copiedUsername, setCopiedUsername] = useState(false);
  const [copiedPassword, setCopiedPassword] = useState(false);

  const generateUsername = () => data.companyName
    ? `${data.companyName.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, "_")}_portal`
    : "";

  const generatePassword = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    return Array.from({ length: 16 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
  };

  const handleTogglePortal = (enabled: boolean) => {
    updateData({ portalEnabled: enabled });
    if (enabled && !data.portalUsername) {
      updateData({ portalUsername: generateUsername(), portalPassword: generatePassword() });
    }
  };

  const copy = (text: string, type: "username" | "password") => {
    navigator.clipboard.writeText(text);
    if (type === "username") { setCopiedUsername(true); setTimeout(() => setCopiedUsername(false), 2000); }
    else { setCopiedPassword(true); setTimeout(() => setCopiedPassword(false), 2000); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Portal Access (Optional)</h3>
        <p className="text-gray-600 dark:text-gray-400">Enable customer portal for self-service access</p>
      </div>
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-3 mb-2">
              <Key className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              <h4 className="text-lg font-semibold text-gray-900 dark:text-white">Enable Customer Portal Access</h4>
            </div>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 mt-2">
              <li>• View ISO certification progress</li>
              <li>• Upload evidence documents</li>
              <li>• Track tasks and deadlines</li>
            </ul>
          </div>
          <button onClick={() => handleTogglePortal(!data.portalEnabled)}
            className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${data.portalEnabled ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"}`}>
            <span className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${data.portalEnabled ? "translate-x-7" : "translate-x-1"}`} />
          </button>
        </div>
      </div>

      {data.portalEnabled && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
          className="space-y-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-semibold text-gray-900 dark:text-white">Portal Credentials</h4>
            <button onClick={() => updateData({ portalUsername: generateUsername(), portalPassword: generatePassword() })}
              className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-700">
              <RefreshCw className="w-4 h-4" /><span>Regenerate</span>
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Username</label>
            <div className="flex space-x-2">
              <input type="text" value={data.portalUsername} onChange={(e) => updateData({ portalUsername: e.target.value })}
                className="flex-1 px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono" />
              <button onClick={() => copy(data.portalUsername, "username")} className="px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
                {copiedUsername ? <Check className="w-5 h-5 text-green-500" /> : <Copy className="w-5 h-5 text-gray-600 dark:text-gray-400" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Password</label>
            <div className="flex space-x-2">
              <div className="flex-1 relative">
                <input type={showPassword ? "text" : "password"} value={data.portalPassword} onChange={(e) => updateData({ portalPassword: e.target.value })}
                  className="w-full px-4 py-3 pr-12 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono" />
                <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500">
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <button onClick={() => copy(data.portalPassword, "password")} className="px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
                {copiedPassword ? <Check className="w-5 h-5 text-green-500" /> : <Copy className="w-5 h-5 text-gray-600 dark:text-gray-400" />}
              </button>
            </div>
          </div>
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 mt-2">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">⚠️ <strong>Save these credentials</strong> — password won't be shown again after creation!</p>
          </div>
        </motion.div>
      )}

      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button onClick={onBack} className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2">
          <ArrowLeft className="w-5 h-5" /><span>Back</span>
        </button>
        <div className="flex space-x-4">
          <button onClick={onSkip} className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white font-medium">Skip</button>
          <button onClick={onNext} className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md flex items-center space-x-2 font-medium">
            <span>Next</span><ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ISOAssignmentStep({ onNext, onBack, onSkip, data, updateData }: WizardStep) {
  const [availableISOs, setAvailableISOs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedISO, setSelectedISO] = useState("");
  const [templateMode, setTemplateMode] = useState<"all" | "selective">("all");
  const [targetDate, setTargetDate] = useState("");
  const [isoTemplates, setIsoTemplates] = useState<any[]>([]);
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  useEffect(() => {
    const fetchISOs = async () => {
      try {
        const response = await api.get("/api/v1/iso-standards");
        setAvailableISOs(response.data);
      } catch (error) {
        console.error("Failed to fetch ISO standards:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchISOs();
  }, []);

  // Fetch approved templates when ISO is selected
  useEffect(() => {
    if (!selectedISO) { setIsoTemplates([]); setSelectedTemplateIds([]); return; }
    const fetchTemplates = async () => {
      setLoadingTemplates(true);
      try {
        const res = await api.get(`/api/v1/iso-standards/${selectedISO}/templates`);
        setIsoTemplates(res.data.filter((t: any) => t.status === "approved"));
      } catch {
        setIsoTemplates([]);
      } finally {
        setLoadingTemplates(false);
      }
    };
    fetchTemplates();
  }, [selectedISO]);

  const toggleTemplate = (id: string) =>
    setSelectedTemplateIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const handleAddISO = () => {
    if (!selectedISO) return;
    const iso = availableISOs.find((i) => i.id === selectedISO);
    if (!iso) return;
    const count = templateMode === "all" ? isoTemplates.length : selectedTemplateIds.length;
    updateData({
      isoAssignments: [...(data.isoAssignments || []), {
        id: selectedISO, iso_code: iso.code, iso_name: iso.name,
        template_mode: templateMode,
        selected_template_ids: templateMode === "selective" ? selectedTemplateIds : null,
        target_date: targetDate || null,
        estimated_documents: count, estimated_tasks: count * 8,
      }]
    });
    setSelectedISO(""); setTemplateMode("all"); setTargetDate("");
    setSelectedTemplateIds([]); setIsoTemplates([]);
    setShowAddModal(false);
  };

  const handleRemoveISO = (isoId: string) =>
    updateData({ isoAssignments: (data.isoAssignments || []).filter((a: any) => a.id !== isoId) });

  const selectedISOObj = availableISOs.find((i) => i.id === selectedISO);
  const approvedCount = selectedISOObj?.approved_template_count || 0;
  const canAdd = !!selectedISO && approvedCount > 0 &&
    (templateMode === "all" || selectedTemplateIds.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">ISO Standards Assignment (Optional)</h3>
        <p className="text-gray-600 dark:text-gray-400">Assign ISO certifications to this customer</p>
      </div>

      <div className="space-y-4">
        {data.isoAssignments?.length > 0 ? data.isoAssignments.map((a: any) => (
          <motion.div key={a.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-5 border border-blue-200 dark:border-blue-800">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <Shield className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                <div>
                  <h4 className="font-bold text-gray-900 dark:text-white">{a.iso_code}</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{a.iso_name}</p>
                  <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                    <span><FileText className="w-3 h-3 inline mr-1" />{a.estimated_documents} template{a.estimated_documents !== 1 ? "s" : ""}</span>
                    <span><CheckSquare className="w-3 h-3 inline mr-1" />~{a.estimated_tasks} tasks</span>
                    {a.target_date && <span><Calendar className="w-3 h-3 inline mr-1" />{new Date(a.target_date).toLocaleDateString()}</span>}
                  </div>
                </div>
              </div>
              <button onClick={() => handleRemoveISO(a.id)} className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg">
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </motion.div>
        )) : (
          <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600">
            <Shield className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600 dark:text-gray-400">No ISO standards assigned yet</p>
            <p className="text-sm text-gray-500 mt-1">You can add ISO certifications now or later</p>
          </div>
        )}
      </div>

      <button onClick={() => setShowAddModal(true)}
        className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all shadow-md flex items-center justify-center space-x-2 font-medium">
        <Plus className="w-5 h-5" /><span>Add ISO Certification</span>
      </button>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-xl font-bold text-gray-900 dark:text-white">Add ISO Certification</h4>
              <button onClick={() => setShowAddModal(false)} className="text-gray-500 hover:text-gray-700"><X className="w-6 h-6" /></button>
            </div>
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Select ISO Standard <span className="text-red-500">*</span></label>
                <select value={selectedISO} onChange={(e) => { setSelectedISO(e.target.value); setTemplateMode("all"); setSelectedTemplateIds([]); }}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white">
                  <option value="">Choose an ISO standard...</option>
                  {availableISOs.filter((iso) => !(data.isoAssignments || []).find((a: any) => a.id === iso.id))
                    .map((iso) => (
                      <option key={iso.id} value={iso.id}>
                        {iso.code} - {iso.name}{(iso.approved_template_count || 0) === 0 ? " (no approved templates)" : ""}
                      </option>
                    ))}
                </select>
                {selectedISO && (
                  approvedCount === 0 ? (
                    <div className="mt-2 flex items-start gap-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-lg px-3 py-2">
                      <span className="text-amber-500 mt-0.5">⚠️</span>
                      <p className="text-sm text-amber-800 dark:text-amber-200">No approved templates yet — assign now but documents won't generate until templates are approved.</p>
                    </div>
                  ) : (
                    <p className="mt-1.5 text-xs text-gray-500">{approvedCount} approved template{approvedCount !== 1 ? "s" : ""} ready</p>
                  )
                )}
              </div>

              {approvedCount > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Template Selection</label>
                  <div className="space-y-3">
                    {(["all", "selective"] as const).map((mode) => (
                      <label key={mode} className={`flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all ${templateMode === mode ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20" : "border-gray-300 dark:border-gray-600"}`}>
                        <input type="radio" name="templateMode" value={mode} checked={templateMode === mode} onChange={() => { setTemplateMode(mode); setSelectedTemplateIds([]); }} className="mt-1 w-4 h-4 text-blue-600" />
                        <div className="ml-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 dark:text-white">{mode === "all" ? "All Templates" : "Selective"}</span>
                            {mode === "all" && <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full">Recommended</span>}
                          </div>
                          <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                            {mode === "all" ? `Include all ${approvedCount} approved templates` : "Pick specific templates to include"}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>

                  {templateMode === "selective" && (
                    <div className="mt-3 border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
                      <div className="bg-gray-50 dark:bg-gray-700 px-4 py-2 flex items-center justify-between">
                        <span className="text-xs font-medium text-gray-600 dark:text-gray-300">Approved Templates</span>
                        <span className="text-xs text-blue-600 dark:text-blue-400">{selectedTemplateIds.length} selected</span>
                      </div>
                      {loadingTemplates ? (
                        <div className="px-4 py-6 text-center text-sm text-gray-500">Loading templates...</div>
                      ) : (
                        <div className="max-h-48 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700">
                          {isoTemplates.map((t: any) => (
                            <label key={t.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                              <input type="checkbox" checked={selectedTemplateIds.includes(t.id)}
                                onChange={() => toggleTemplate(t.id)}
                                className="w-4 h-4 text-blue-600 rounded" />
                              <span className="text-sm text-gray-800 dark:text-gray-200 flex-1">{t.name}</span>
                              {t.total_fillable_sections > 0 && (
                                <span className="text-xs text-gray-400">{t.total_fillable_sections} fields</span>
                              )}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Target Completion Date (Optional)</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white" />
                </div>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setShowAddModal(false)} className="px-6 py-2.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">Cancel</button>
              <button onClick={handleAddISO} disabled={!canAdd}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2">
                <Plus className="w-4 h-4" /><span>Add ISO</span>
              </button>
            </div>
          </motion.div>
        </div>
      )}

      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button onClick={onBack} className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2">
          <ArrowLeft className="w-5 h-5" /><span>Back</span>
        </button>
        <div className="flex space-x-4">
          <button onClick={onSkip} className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white font-medium">Skip for Now</button>
          <button onClick={onNext} className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md flex items-center space-x-2 font-medium">
            <span>Review & Create</span><ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ReviewStep({ onBack, data, onSuccess, onClose }: any) {
  const [creating, setCreating] = useState(false);
  const [copiedUsername, setCopiedUsername] = useState(false);
  const [copiedPassword, setCopiedPassword] = useState(false);

  const copy = (text: string, type: "username" | "password") => {
    navigator.clipboard.writeText(text);
    if (type === "username") { setCopiedUsername(true); setTimeout(() => setCopiedUsername(false), 2000); }
    else { setCopiedPassword(true); setTimeout(() => setCopiedPassword(false), 2000); }
  };

  const handleCreateCustomer = async () => {
    setCreating(true);
    try {
      const payload = {
        name: data.companyName,
        website: data.website || null,
        contact_person: data.contactPerson || null,
        phone: data.phone || null,
        address: data.address || null,
        description: data.description || null,
        email: data.email,
        contact_email: data.contactEmail || data.email,
        document_email: data.documentEmail || data.email,
        compliance_email: data.complianceEmail || null,
        contract_email: data.contractEmail || null,
        storage_type: data.storageType,
        portal_enabled: data.portalEnabled,
        portal_username: data.portalEnabled ? data.portalUsername : null,
        portal_password: data.portalEnabled ? data.portalPassword : null,
        iso_assignments: data.isoAssignments?.length > 0
          ? data.isoAssignments.map((iso: any) => ({
              iso_standard_id: iso.id,
              template_selection_mode: iso.template_mode,
              selected_template_ids: iso.selected_template_ids || null,
              target_completion_date: iso.target_date || null,
            }))
          : null,
      };

      const res = await api.post("/api/v1/iso-customers", payload);
      const result = res.data;
      onSuccess(result.customer);
      onClose();
    } catch (error: any) {
      console.error("Error creating customer:", error);
      alert(error.message || "Failed to create customer. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Review & Confirm</h3>
        <p className="text-gray-600 dark:text-gray-400">Please review all information before creating the customer</p>
      </div>

      <div className="space-y-5">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Building2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h4 className="font-semibold text-gray-900 dark:text-white">Company Information</h4>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-gray-500">Company Name</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.companyName}</p></div>
            {data.website && <div><span className="text-gray-500">Website</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.website}</p></div>}
            {data.contactPerson && <div><span className="text-gray-500">Contact Person</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.contactPerson}</p></div>}
            {data.phone && <div><span className="text-gray-500">Phone</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.phone}</p></div>}
            {data.address && <div className="col-span-2"><span className="text-gray-500">Address</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.address}</p></div>}
            {data.description && <div className="col-span-2"><span className="text-gray-500">Description</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.description}</p></div>}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Mail className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h4 className="font-semibold text-gray-900 dark:text-white">Contact & Communication</h4>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-gray-500">Primary Email</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.email}</p></div>
            <div><span className="text-gray-500">Contact Email</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.contactEmail || data.email}</p></div>
            <div><span className="text-gray-500">Document Email</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.documentEmail || data.email}</p></div>
            {data.complianceEmail && <div><span className="text-gray-500">Compliance Email</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.complianceEmail}</p></div>}
            {data.contractEmail && <div><span className="text-gray-500">Contract Email</span><p className="font-medium text-gray-900 dark:text-white mt-1">{data.contractEmail}</p></div>}
          </div>
        </div>

        {data.portalEnabled && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
            <div className="flex items-center space-x-3 mb-4">
              <Key className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-gray-900 dark:text-white">Portal Access Credentials</h4>
            </div>
            <div className="space-y-3">
              {[{ label: "Username", value: data.portalUsername, type: "username" as const },
                { label: "Password", value: data.portalPassword, type: "password" as const }].map(({ label, value, type }) => (
                <div key={type} className="bg-white dark:bg-gray-800 rounded-lg p-3">
                  <span className="text-xs text-gray-500 block mb-1">{label}</span>
                  <div className="flex items-center justify-between">
                    <code className="text-sm font-mono text-gray-900 dark:text-white">{value}</code>
                    <button onClick={() => copy(value, type)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                      {(type === "username" ? copiedUsername : copiedPassword)
                        ? <Check className="w-4 h-4 text-green-500" />
                        : <Copy className="w-4 h-4 text-gray-600 dark:text-gray-400" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
              <p className="text-xs text-yellow-800 dark:text-yellow-200">⚠️ Save these credentials — they won't be shown again!</p>
            </div>
          </div>
        )}

        {data.isoAssignments?.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-3 mb-4">
              <Shield className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-gray-900 dark:text-white">ISO Certifications ({data.isoAssignments.length})</h4>
            </div>
            <div className="space-y-3">
              {data.isoAssignments.map((iso: any, i: number) => (
                <div key={i} className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{iso.iso_code}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">{iso.iso_name}</p>
                    <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                      <span><FileText className="w-3 h-3 inline mr-1" />~{iso.estimated_documents} docs</span>
                      <span><CheckSquare className="w-3 h-3 inline mr-1" />~{iso.estimated_tasks} tasks</span>
                      {iso.target_date && <span><Calendar className="w-3 h-3 inline mr-1" />{new Date(iso.target_date).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-full">
                    {iso.template_mode === "all" ? "All Templates" : "Selective"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-6 border border-green-200 dark:border-green-800">
        <div className="flex items-center space-x-3 mb-4">
          <Sparkles className="w-5 h-5 text-green-600 dark:text-green-400" />
          <h4 className="font-semibold text-gray-900 dark:text-white">Ready to Create</h4>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div><p className="text-2xl font-bold text-gray-900 dark:text-white">{data.isoAssignments?.length || 0}</p><p className="text-sm text-gray-600 dark:text-gray-400">ISO Plans</p></div>
          <div><p className="text-2xl font-bold text-gray-900 dark:text-white">~{data.isoAssignments?.reduce((s: number, i: any) => s + i.estimated_documents, 0) || 0}</p><p className="text-sm text-gray-600 dark:text-gray-400">Total Documents</p></div>
          <div><p className="text-2xl font-bold text-gray-900 dark:text-white">~{data.isoAssignments?.reduce((s: number, i: any) => s + i.estimated_tasks, 0) || 0}</p><p className="text-sm text-gray-600 dark:text-gray-400">Total Tasks</p></div>
        </div>
      </div>

      <div className="flex justify-between pt-6 border-t border-gray-200 dark:border-gray-700">
        <button onClick={onBack} disabled={creating}
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center space-x-2 disabled:opacity-50">
          <ArrowLeft className="w-5 h-5" /><span>Back</span>
        </button>
        <button onClick={handleCreateCustomer} disabled={creating}
          className="px-8 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg flex items-center space-x-2 font-semibold disabled:opacity-50">
          {creating ? <><RefreshCw className="w-5 h-5 animate-spin" /><span>Creating...</span></> : <><span>Create Customer</span><CheckCircle2 className="w-5 h-5" /></>}
        </button>
      </div>
    </div>
  );
}
