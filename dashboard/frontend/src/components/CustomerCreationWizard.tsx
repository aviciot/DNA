"use client";

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2,
  Mail,
  Key,
  Shield,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  X,
  Eye,
  EyeOff,
  RefreshCw,
  Copy,
  Check,
  Plus,
  Trash2,
  Calendar,
  FileText,
  CheckSquare,
  Sparkles,
} from "lucide-react";

// Step definitions
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

export default function CustomerCreationWizard({
  isOpen,
  onClose,
  onSuccess,
}: CustomerCreationWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [wizardData, setWizardData] = useState({
    // Step 1: Company Info
    companyName: "",
    website: "",
    contactPerson: "",
    phone: "",
    address: "",

    // Step 2: Contact & Communication
    email: "",
    contactEmail: "",
    documentEmail: "",
    storageType: "local",

    // Step 3: Portal Access
    portalEnabled: false,
    portalUsername: "",
    portalPassword: "",

    // Step 4: ISO Standards
    isoAssignments: [],

    // Step 5: Review
    confirmed: false,
  });

  const updateWizardData = useCallback((data: Partial<typeof wizardData>) => {
    setWizardData((prev) => ({ ...prev, ...data }));
  }, []);

  const handleNext = useCallback(() => {
    if (currentStep < STEPS.length) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep]);

  const handleBack = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

  const handleSkip = useCallback(() => {
    if (currentStep < STEPS.length) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep]);

  const handleClose = useCallback(() => {
    if (confirm("Are you sure you want to cancel customer creation?")) {
      onClose();
      setCurrentStep(1);
      setWizardData({
        companyName: "",
        website: "",
        contactPerson: "",
        phone: "",
        address: "",
        email: "",
        contactEmail: "",
        documentEmail: "",
        storageType: "local",
        portalEnabled: false,
        portalUsername: "",
        portalPassword: "",
        isoAssignments: [],
        confirmed: false,
      });
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
        {/* Header */}
        <div className="relative bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 px-8 py-6">
          <button
            onClick={handleClose}
            className="absolute top-6 right-6 text-white/80 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>

          <h2 className="text-3xl font-bold text-white mb-2">
            Create New Customer
          </h2>
          <p className="text-blue-100">
            Set up a new customer with ISO certification management
          </p>
        </div>

        {/* Progress Stepper */}
        <div className="px-8 py-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  {/* Step Circle */}
                  <motion.div
                    initial={false}
                    animate={{
                      scale: currentStep === step.id ? 1.1 : 1,
                      backgroundColor:
                        currentStep >= step.id
                          ? "rgb(37, 99, 235)"
                          : "rgb(229, 231, 235)",
                    }}
                    className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                      currentStep >= step.id
                        ? "bg-blue-600 text-white shadow-lg shadow-blue-500/50"
                        : "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400"
                    }`}
                  >
                    {currentStep > step.id ? (
                      <CheckCircle2 className="w-6 h-6" />
                    ) : (
                      <step.icon className="w-6 h-6" />
                    )}
                  </motion.div>

                  {/* Step Label */}
                  <span
                    className={`mt-2 text-sm font-medium ${
                      currentStep >= step.id
                        ? "text-blue-600 dark:text-blue-400"
                        : "text-gray-500 dark:text-gray-400"
                    }`}
                  >
                    {step.name}
                  </span>
                </div>

                {/* Connector Line */}
                {index < STEPS.length - 1 && (
                  <motion.div
                    initial={false}
                    animate={{
                      backgroundColor:
                        currentStep > step.id
                          ? "rgb(37, 99, 235)"
                          : "rgb(229, 231, 235)",
                    }}
                    className="h-1 flex-1 mx-2 rounded-full"
                    style={{ marginTop: "-2.5rem" }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="px-8 py-6 overflow-y-auto" style={{ maxHeight: "calc(90vh - 280px)" }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
            >
              {currentStep === 1 && (
                <CompanyInfoStep
                  onNext={handleNext}
                  onBack={handleBack}
                  data={wizardData}
                  updateData={updateWizardData}
                />
              )}
              {currentStep === 2 && (
                <ContactStep
                  onNext={handleNext}
                  onBack={handleBack}
                  data={wizardData}
                  updateData={updateWizardData}
                />
              )}
              {currentStep === 3 && (
                <PortalStep
                  onNext={handleNext}
                  onBack={handleBack}
                  onSkip={handleSkip}
                  data={wizardData}
                  updateData={updateWizardData}
                />
              )}
              {currentStep === 4 && (
                <ISOAssignmentStep
                  onNext={handleNext}
                  onBack={handleBack}
                  onSkip={handleSkip}
                  data={wizardData}
                  updateData={updateWizardData}
                />
              )}
              {currentStep === 5 && (
                <ReviewStep
                  onBack={handleBack}
                  data={wizardData}
                  onSuccess={onSuccess}
                  onClose={onClose}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}

// Step Components
function CompanyInfoStep({ onNext, data, updateData }: WizardStep) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!data.companyName?.trim()) {
      newErrors.companyName = "Company name is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      onNext();
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Company Information
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Tell us about the company you're onboarding
        </p>
      </div>

      <div className="space-y-5">
        {/* Company Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Company Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={data.companyName}
            onChange={(e) => updateData({ companyName: e.target.value })}
            placeholder="Acme Corporation"
            className={`w-full px-4 py-3 rounded-lg border ${
              errors.companyName
                ? "border-red-500 focus:ring-red-500"
                : "border-gray-300 dark:border-gray-600 focus:ring-blue-500"
            } focus:ring-2 focus:ring-offset-0 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 transition-all`}
          />
          {errors.companyName && (
            <p className="mt-1 text-sm text-red-500">{errors.companyName}</p>
          )}
        </div>

        {/* Website */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Website
          </label>
          <input
            type="url"
            value={data.website}
            onChange={(e) => updateData({ website: e.target.value })}
            placeholder="https://www.acmecorp.com"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>

        {/* Contact Person */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Contact Person
          </label>
          <input
            type="text"
            value={data.contactPerson}
            onChange={(e) => updateData({ contactPerson: e.target.value })}
            placeholder="John Smith"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>

        {/* Phone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Phone
          </label>
          <input
            type="tel"
            value={data.phone}
            onChange={(e) => updateData({ phone: e.target.value })}
            placeholder="+1-555-0123"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>

        {/* Address */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Address
          </label>
          <textarea
            value={data.address}
            onChange={(e) => updateData({ address: e.target.value })}
            placeholder="123 Main Street, New York, NY 10001"
            rows={3}
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 resize-none"
          />
        </div>
      </div>

      <div className="flex justify-end space-x-4 mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={handleNext}
          className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md hover:shadow-lg flex items-center space-x-2 font-medium"
        >
          <span>Next</span>
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

function ContactStep({ onNext, onBack, data, updateData }: WizardStep) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!data.email?.trim()) {
      newErrors.email = "Primary email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
      newErrors.email = "Invalid email format";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      // Auto-fill emails if not set
      if (!data.contactEmail) {
        updateData({ contactEmail: data.email });
      }
      if (!data.documentEmail) {
        updateData({ documentEmail: data.email });
      }
      onNext();
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Contact & Communication
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          How should we communicate with this customer?
        </p>
      </div>

      <div className="space-y-5">
        {/* Primary Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Primary Email <span className="text-red-500">*</span>
          </label>
          <input
            type="email"
            value={data.email}
            onChange={(e) => updateData({ email: e.target.value })}
            placeholder="john@acmecorp.com"
            className={`w-full px-4 py-3 rounded-lg border ${
              errors.email
                ? "border-red-500 focus:ring-red-500"
                : "border-gray-300 dark:border-gray-600 focus:ring-blue-500"
            } focus:ring-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400`}
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-500">{errors.email}</p>
          )}
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Used for login and notifications
          </p>
        </div>

        {/* Contact Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Contact Email
          </label>
          <input
            type="email"
            value={data.contactEmail}
            onChange={(e) => updateData({ contactEmail: e.target.value })}
            placeholder="Leave empty to use primary email"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            For general communication
          </p>
        </div>

        {/* Document Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Document Email
          </label>
          <input
            type="email"
            value={data.documentEmail}
            onChange={(e) => updateData({ documentEmail: e.target.value })}
            placeholder="compliance@acmecorp.com"
            className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            For sending/receiving documents
          </p>
        </div>

        {/* Storage Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Storage Type
          </label>
          <div className="space-y-3">
            <label className="flex items-center p-4 rounded-lg border-2 border-blue-500 bg-blue-50 dark:bg-blue-900/20 cursor-pointer">
              <input
                type="radio"
                name="storage"
                value="local"
                checked={data.storageType === "local"}
                onChange={(e) => updateData({ storageType: e.target.value })}
                className="w-4 h-4 text-blue-600"
              />
              <div className="ml-3 flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900 dark:text-white">
                    Local Storage
                  </span>
                  <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded-full">
                    Recommended
                  </span>
                </div>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Files stored on server filesystem
                </span>
              </div>
            </label>

            <label className="flex items-center p-4 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 opacity-60 cursor-not-allowed">
              <input
                type="radio"
                disabled
                className="w-4 h-4"
              />
              <div className="ml-3">
                <div className="font-medium text-gray-500 dark:text-gray-400">
                  Google Drive
                </div>
                <span className="text-sm text-gray-400">Coming Soon</span>
              </div>
            </label>
          </div>
        </div>
      </div>

      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center space-x-2"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back</span>
        </button>
        <button
          onClick={handleNext}
          className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md hover:shadow-lg flex items-center space-x-2 font-medium"
        >
          <span>Next</span>
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

function PortalStep({ onNext, onBack, onSkip, data, updateData }: WizardStep) {
  const [showPassword, setShowPassword] = useState(false);
  const [copiedUsername, setCopiedUsername] = useState(false);
  const [copiedPassword, setCopiedPassword] = useState(false);

  // Generate username from company name
  const generateUsername = () => {
    if (!data.companyName) return "";
    const sanitized = data.companyName
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, "")
      .replace(/\s+/g, "_");
    return `${sanitized}_portal`;
  };

  // Generate random password
  const generatePassword = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
  };

  // Auto-generate credentials when portal is enabled
  const handleTogglePortal = (enabled: boolean) => {
    updateData({ portalEnabled: enabled });
    if (enabled && !data.portalUsername) {
      updateData({
        portalUsername: generateUsername(),
        portalPassword: generatePassword(),
      });
    }
  };

  const handleRegenerateCredentials = () => {
    updateData({
      portalUsername: generateUsername(),
      portalPassword: generatePassword(),
    });
  };

  const copyToClipboard = (text: string, type: "username" | "password") => {
    navigator.clipboard.writeText(text);
    if (type === "username") {
      setCopiedUsername(true);
      setTimeout(() => setCopiedUsername(false), 2000);
    } else {
      setCopiedPassword(true);
      setTimeout(() => setCopiedPassword(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Portal Access (Optional)
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Enable customer portal for self-service access
        </p>
      </div>

      {/* Portal Toggle */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-3 mb-2">
              <Key className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                Enable Customer Portal Access
              </h4>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              When enabled, customers can:
            </p>
            <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <li>• View their ISO certification progress</li>
              <li>• Upload evidence documents</li>
              <li>• Track tasks and deadlines</li>
            </ul>
          </div>
          <button
            onClick={() => handleTogglePortal(!data.portalEnabled)}
            className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
              data.portalEnabled ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span
              className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                data.portalEnabled ? "translate-x-7" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Credentials (shown when portal is enabled) */}
      {data.portalEnabled && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="space-y-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-semibold text-gray-900 dark:text-white">
              Portal Credentials
            </h4>
            <button
              onClick={handleRegenerateCredentials}
              className="flex items-center space-x-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Regenerate</span>
            </button>
          </div>

          {/* Username */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Username
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={data.portalUsername}
                onChange={(e) => updateData({ portalUsername: e.target.value })}
                className="flex-1 px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono"
              />
              <button
                onClick={() => copyToClipboard(data.portalUsername, "username")}
                className="px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                {copiedUsername ? (
                  <Check className="w-5 h-5 text-green-500" />
                ) : (
                  <Copy className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                )}
              </button>
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Password
            </label>
            <div className="flex space-x-2">
              <div className="flex-1 relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={data.portalPassword}
                  onChange={(e) => updateData({ portalPassword: e.target.value })}
                  className="w-full px-4 py-3 pr-12 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white font-mono"
                />
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
              <button
                onClick={() => copyToClipboard(data.portalPassword, "password")}
                className="px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                {copiedPassword ? (
                  <Check className="w-5 h-5 text-green-500" />
                ) : (
                  <Copy className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                )}
              </button>
            </div>
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mt-4">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              ⚠️ <strong>Save these credentials</strong> - the password won't be shown again after customer creation!
            </p>
          </div>
        </motion.div>
      )}

      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center space-x-2"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back</span>
        </button>
        <div className="flex space-x-4">
          <button
            onClick={onSkip}
            className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors font-medium"
          >
            Skip
          </button>
          <button
            onClick={onNext}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md hover:shadow-lg flex items-center space-x-2 font-medium"
          >
            <span>Next</span>
            <ArrowRight className="w-5 h-5" />
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
  const [selectedISO, setSelectedISO] = useState<string>("");
  const [templateMode, setTemplateMode] = useState<"all" | "selective">("all");
  const [targetDate, setTargetDate] = useState("");
  const [generationPreview, setGenerationPreview] = useState<any>(null);

  // Fetch available ISO standards
  useEffect(() => {
    const fetchISOs = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";
        const token = localStorage.getItem("access_token");

        const response = await fetch(`${apiUrl}/api/v1/iso-standards`, {
          headers: {
            "Authorization": token ? `Bearer ${token}` : "",
            "Content-Type": "application/json"
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }

        const result = await response.json();
        setAvailableISOs(result);
      } catch (error) {
        console.error("Failed to fetch ISO standards:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchISOs();
  }, []);

  const handleAddISO = () => {
    if (!selectedISO) return;

    const iso = availableISOs.find((i) => i.id === selectedISO);
    if (!iso) return;

    const templateCount = iso.template_count || 0;
    const estimatedTasksPerTemplate = 8; // Average tasks per template

    const newAssignment = {
      id: selectedISO,
      iso_code: iso.code,
      iso_name: iso.name,
      template_mode: templateMode,
      target_date: targetDate || null,
      estimated_documents: templateMode === "all" ? templateCount : Math.ceil(templateCount * 0.5),
      estimated_tasks: templateMode === "all"
        ? templateCount * estimatedTasksPerTemplate
        : Math.ceil(templateCount * 0.5 * estimatedTasksPerTemplate),
    };

    const currentAssignments = data.isoAssignments || [];
    updateData({ isoAssignments: [...currentAssignments, newAssignment] });

    // Reset form
    setSelectedISO("");
    setTemplateMode("all");
    setTargetDate("");
    setShowAddModal(false);
  };

  const handleRemoveISO = (isoId: string) => {
    const updatedAssignments = (data.isoAssignments || []).filter(
      (assignment: any) => assignment.id !== isoId
    );
    updateData({ isoAssignments: updatedAssignments });
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          ISO Standards Assignment (Optional)
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Assign ISO certifications to this customer
        </p>
      </div>

      {/* Current Assignments */}
      <div className="space-y-4">
        {data.isoAssignments && data.isoAssignments.length > 0 ? (
          data.isoAssignments.map((assignment: any) => (
            <motion.div
              key={assignment.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-3">
                    <Shield className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                    <div>
                      <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                        {assignment.iso_code}
                      </h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {assignment.iso_name}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400 mb-1">
                        <FileText className="w-4 h-4" />
                        <span>Documents</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        ~{assignment.estimated_documents}
                      </p>
                    </div>

                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400 mb-1">
                        <CheckSquare className="w-4 h-4" />
                        <span>Tasks</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        ~{assignment.estimated_tasks}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    <div className="flex items-center space-x-2 text-gray-700 dark:text-gray-300">
                      <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      <span>
                        Template Mode:{" "}
                        <span className="font-medium">
                          {assignment.template_mode === "all"
                            ? "All Templates"
                            : "Selective Templates"}
                        </span>
                      </span>
                    </div>
                    {assignment.target_date && (
                      <div className="flex items-center space-x-2 text-gray-700 dark:text-gray-300">
                        <Calendar className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                        <span>
                          Target Date:{" "}
                          <span className="font-medium">
                            {new Date(assignment.target_date).toLocaleDateString()}
                          </span>
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => handleRemoveISO(assignment.id)}
                  className="ml-4 p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                  title="Remove ISO assignment"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </motion.div>
          ))
        ) : (
          <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600">
            <Shield className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600 dark:text-gray-400">
              No ISO standards assigned yet
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
              You can add ISO certifications now or later
            </p>
          </div>
        )}
      </div>

      {/* Add ISO Button */}
      <button
        onClick={() => setShowAddModal(true)}
        className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all shadow-md hover:shadow-lg flex items-center justify-center space-x-2 font-medium"
      >
        <Plus className="w-5 h-5" />
        <span>Add ISO Certification</span>
      </button>

      {/* Add ISO Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl p-6"
          >
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-xl font-bold text-gray-900 dark:text-white">
                Add ISO Certification
              </h4>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-5">
              {/* ISO Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Select ISO Standard <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedISO}
                  onChange={(e) => setSelectedISO(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="">Choose an ISO standard...</option>
                  {availableISOs
                    .filter(
                      (iso) =>
                        !(data.isoAssignments || []).find((a: any) => a.id === iso.id)
                    )
                    .map((iso) => (
                      <option key={iso.id} value={iso.id}>
                        {iso.code} - {iso.name}
                      </option>
                    ))}
                </select>
              </div>

              {/* Template Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Template Selection Mode
                </label>
                <div className="space-y-3">
                  <label
                    className={`flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all ${
                      templateMode === "all"
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="templateMode"
                      value="all"
                      checked={templateMode === "all"}
                      onChange={(e) => setTemplateMode(e.target.value as "all")}
                      className="mt-1 w-4 h-4 text-blue-600"
                    />
                    <div className="ml-3 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900 dark:text-white">
                          All Templates
                        </span>
                        <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded-full">
                          Recommended
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        Generate all required documents and tasks for full compliance
                      </p>
                    </div>
                  </label>

                  <label
                    className={`flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all ${
                      templateMode === "selective"
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="templateMode"
                      value="selective"
                      checked={templateMode === "selective"}
                      onChange={(e) => setTemplateMode(e.target.value as "selective")}
                      className="mt-1 w-4 h-4 text-blue-600"
                    />
                    <div className="ml-3 flex-1">
                      <span className="font-medium text-gray-900 dark:text-white">
                        Selective Templates
                      </span>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        Choose specific templates (can be configured after creation)
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Target Date */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Target Completion Date (Optional)
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Preview Info */}
              {selectedISO && (() => {
                const iso = availableISOs.find((i) => i.id === selectedISO);
                const templateCount = iso?.template_count || 0;
                const estimatedDocs = templateMode === "all" ? templateCount : Math.ceil(templateCount * 0.5);
                const estimatedTasks = estimatedDocs * 8; // 8 tasks per template average

                return (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800"
                  >
                    <div className="flex items-start space-x-3">
                      <Sparkles className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5" />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white mb-2">
                          Generation Preview
                        </p>
                        <p className="text-sm text-gray-700 dark:text-gray-300">
                          This will create approximately{" "}
                          <span className="font-bold">
                            {estimatedDocs} document{estimatedDocs !== 1 ? "s" : ""}
                          </span>{" "}
                          and{" "}
                          <span className="font-bold">
                            ~{estimatedTasks} tasks
                          </span>
                        </p>
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                          You can generate documents now or later from the customer dashboard
                        </p>
                      </div>
                    </div>
                  </motion.div>
                );
              })()}
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-6 py-2.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddISO}
                disabled={!selectedISO}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                <Plus className="w-4 h-4" />
                <span>Add ISO</span>
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center space-x-2"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back</span>
        </button>
        <div className="flex space-x-4">
          <button
            onClick={onSkip}
            className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors font-medium"
          >
            Skip for Now
          </button>
          <button
            onClick={onNext}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md hover:shadow-lg flex items-center space-x-2 font-medium"
          >
            <span>Review & Create</span>
            <ArrowRight className="w-5 h-5" />
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

  const copyToClipboard = (text: string, type: "username" | "password") => {
    navigator.clipboard.writeText(text);
    if (type === "username") {
      setCopiedUsername(true);
      setTimeout(() => setCopiedUsername(false), 2000);
    } else {
      setCopiedPassword(true);
      setTimeout(() => setCopiedPassword(false), 2000);
    }
  };

  const handleCreateCustomer = async () => {
    setCreating(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";
      const token = localStorage.getItem("access_token");
      const headers = {
        "Content-Type": "application/json",
        "Authorization": token ? `Bearer ${token}` : ""
      };

      // Create customer
      const customerPayload = {
        name: data.companyName,
        website: data.website,
        contact_person: data.contactPerson,
        phone: data.phone,
        address: data.address,
        email: data.email,
        contact_email: data.contactEmail || data.email,
        document_email: data.documentEmail || data.email,
        storage_type: data.storageType,
        portal_enabled: data.portalEnabled,
        portal_username: data.portalEnabled ? data.portalUsername : null,
        portal_password: data.portalEnabled ? data.portalPassword : null,
      };

      const customerResponse = await fetch(`${apiUrl}/api/v1/iso-customers`, {
        method: "POST",
        headers,
        body: JSON.stringify(customerPayload),
      });

      if (!customerResponse.ok) {
        const errorData = await customerResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to create customer");
      }

      const customer = await customerResponse.json();

      // Create ISO plans if any
      if (data.isoAssignments && data.isoAssignments.length > 0) {
        for (const iso of data.isoAssignments) {
          const planResponse = await fetch(`${apiUrl}/api/v1/iso-plans`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              customer_id: customer.id,
              iso_standard_id: iso.id,
              template_selection_mode: iso.template_mode,
              target_completion_date: iso.target_date,
              auto_generate_documents: false, // User can generate later
            }),
          });

          if (!planResponse.ok) {
            console.error(`Failed to create ISO plan for ${iso.iso_code}`);
          }
        }
      }

      onSuccess(customer);
      onClose();
    } catch (error) {
      console.error("Error creating customer:", error);
      alert("Failed to create customer. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Review & Confirm
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Please review all information before creating the customer
        </p>
      </div>

      <div className="space-y-5">
        {/* Company Information */}
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <Building2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-gray-900 dark:text-white">
                Company Information
              </h4>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Company Name</span>
              <p className="font-medium text-gray-900 dark:text-white mt-1">
                {data.companyName}
              </p>
            </div>
            {data.website && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Website</span>
                <p className="font-medium text-gray-900 dark:text-white mt-1">
                  {data.website}
                </p>
              </div>
            )}
            {data.contactPerson && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Contact Person</span>
                <p className="font-medium text-gray-900 dark:text-white mt-1">
                  {data.contactPerson}
                </p>
              </div>
            )}
            {data.phone && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Phone</span>
                <p className="font-medium text-gray-900 dark:text-white mt-1">
                  {data.phone}
                </p>
              </div>
            )}
            {data.address && (
              <div className="col-span-2">
                <span className="text-gray-500 dark:text-gray-400">Address</span>
                <p className="font-medium text-gray-900 dark:text-white mt-1">
                  {data.address}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Contact Information */}
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3 mb-4">
            <Mail className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h4 className="font-semibold text-gray-900 dark:text-white">
              Contact & Communication
            </h4>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Primary Email</span>
              <p className="font-medium text-gray-900 dark:text-white mt-1">
                {data.email}
              </p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Contact Email</span>
              <p className="font-medium text-gray-900 dark:text-white mt-1">
                {data.contactEmail || data.email}
              </p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Document Email</span>
              <p className="font-medium text-gray-900 dark:text-white mt-1">
                {data.documentEmail || data.email}
              </p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Storage Type</span>
              <p className="font-medium text-gray-900 dark:text-white mt-1 capitalize">
                {data.storageType}
              </p>
            </div>
          </div>
        </div>

        {/* Portal Access */}
        {data.portalEnabled && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
            <div className="flex items-center space-x-3 mb-4">
              <Key className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-gray-900 dark:text-white">
                Portal Access Credentials
              </h4>
            </div>
            <div className="space-y-3">
              <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">
                  Username
                </span>
                <div className="flex items-center justify-between">
                  <code className="text-sm font-mono text-gray-900 dark:text-white">
                    {data.portalUsername}
                  </code>
                  <button
                    onClick={() => copyToClipboard(data.portalUsername, "username")}
                    className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                  >
                    {copiedUsername ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                    )}
                  </button>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg p-3">
                <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">
                  Password
                </span>
                <div className="flex items-center justify-between">
                  <code className="text-sm font-mono text-gray-900 dark:text-white">
                    {data.portalPassword}
                  </code>
                  <button
                    onClick={() => copyToClipboard(data.portalPassword, "password")}
                    className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                  >
                    {copiedPassword ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                    )}
                  </button>
                </div>
              </div>
            </div>
            <div className="mt-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
              <p className="text-xs text-yellow-800 dark:text-yellow-200">
                ⚠️ Make sure to save these credentials - they won't be shown again!
              </p>
            </div>
          </div>
        )}

        {/* ISO Assignments */}
        {data.isoAssignments && data.isoAssignments.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-3 mb-4">
              <Shield className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-gray-900 dark:text-white">
                ISO Certifications ({data.isoAssignments.length})
              </h4>
            </div>
            <div className="space-y-3">
              {data.isoAssignments.map((iso: any, index: number) => (
                <div
                  key={index}
                  className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-white">
                        {iso.iso_code}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                        {iso.iso_name}
                      </p>
                      <div className="flex items-center space-x-4 mt-2 text-xs text-gray-600 dark:text-gray-400">
                        <span>
                          <FileText className="w-3 h-3 inline mr-1" />
                          ~{iso.estimated_documents} docs
                        </span>
                        <span>
                          <CheckSquare className="w-3 h-3 inline mr-1" />
                          ~{iso.estimated_tasks} tasks
                        </span>
                        {iso.target_date && (
                          <span>
                            <Calendar className="w-3 h-3 inline mr-1" />
                            {new Date(iso.target_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-full">
                      {iso.template_mode === "all" ? "All Templates" : "Selective"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              <p className="text-xs text-blue-800 dark:text-blue-200">
                💡 Documents and tasks can be generated after customer creation from the
                customer dashboard
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-6 border border-green-200 dark:border-green-800">
        <div className="flex items-center space-x-3 mb-4">
          <Sparkles className="w-5 h-5 text-green-600 dark:text-green-400" />
          <h4 className="font-semibold text-gray-900 dark:text-white">
            Ready to Create
          </h4>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {data.isoAssignments?.length || 0}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">ISO Plans</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              ~
              {data.isoAssignments?.reduce(
                (sum: number, iso: any) => sum + iso.estimated_documents,
                0
              ) || 0}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">Total Documents</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              ~
              {data.isoAssignments?.reduce(
                (sum: number, iso: any) => sum + iso.estimated_tasks,
                0
              ) || 0}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">Total Tasks</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={onBack}
          disabled={creating}
          className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back</span>
        </button>
        <button
          onClick={handleCreateCustomer}
          disabled={creating}
          className="px-8 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/50 flex items-center space-x-2 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {creating ? (
            <>
              <RefreshCw className="w-5 h-5 animate-spin" />
              <span>Creating...</span>
            </>
          ) : (
            <>
              <span>Create Customer</span>
              <CheckCircle2 className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
