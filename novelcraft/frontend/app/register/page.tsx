"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

interface FieldErrors {
  username?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  full_name?: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading, error, clearError } = useAuthStore();

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    full_name: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const validateField = useCallback((name: string, value: string, allData = formData) => {
    let error = "";
    switch (name) {
      case "username":
        if (!value) {
          error = "请输入用户名";
        } else if (value.length < 3) {
          error = "用户名至少需要 3 个字符";
        } else if (value.length > 50) {
          error = "用户名最多 50 个字符";
        } else if (!/^[a-zA-Z0-9_-]+$/.test(value)) {
          error = "用户名只能包含字母、数字、下划线和连字符";
        }
        break;
      case "email":
        if (!value) {
          error = "请输入邮箱";
        } else if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(value)) {
          error = "请输入有效的邮箱地址";
        }
        break;
      case "password":
        if (!value) {
          error = "请输入密码";
        } else if (value.length < 8) {
          error = "密码至少需要 8 个字符";
        } else if (value.length > 72) {
          error = "密码最多 72 个字符";
        }
        break;
      case "confirmPassword":
        if (!value) {
          error = "请确认密码";
        } else if (value !== allData.password) {
          error = "两次输入的密码不一致";
        }
        break;
    }
    return error;
  }, [formData]);

  const getPasswordStrength = (password: string) => {
    if (!password) return { level: 0, label: "", color: "" };
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    if (score <= 1) return { level: 1, label: "弱", color: "bg-red-400" };
    if (score <= 2) return { level: 2, label: "中", color: "bg-yellow-400" };
    if (score <= 3) return { level: 3, label: "强", color: "bg-green-400" };
    return { level: 4, label: "很强", color: "bg-green-600" };
  };

  const validateAllFields = () => {
    const errors: FieldErrors = {};
    const fields = ["username", "email", "password", "confirmPassword"] as const;
    for (const field of fields) {
      const err = validateField(field, formData[field as keyof typeof formData]);
      if (err) errors[field] = err;
    }
    setFieldErrors(errors);
    // Mark all as touched
    const allTouched: Record<string, boolean> = {};
    fields.forEach((f) => { allTouched[f] = true; });
    setTouched(allTouched);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (!validateAllFields()) {
      return;
    }

    try {
      await register(
        formData.username,
        formData.email,
        formData.password,
        formData.full_name || undefined
      );

      alert("注册成功！请登录");
      router.push("/login");
    } catch (err) {
      // Error is handled by the store
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    const newData = { ...formData, [name]: value };
    setFormData(newData);

    // Real-time validation if field was touched
    if (touched[name]) {
      const err = validateField(name, value, newData);
      setFieldErrors((prev) => ({ ...prev, [name]: err || undefined }));

      // Also re-validate confirmPassword when password changes
      if (name === "password" && touched.confirmPassword) {
        const confirmErr = validateField("confirmPassword", newData.confirmPassword, newData);
        setFieldErrors((prev) => ({ ...prev, confirmPassword: confirmErr || undefined }));
      }
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    const err = validateField(name, value);
    setFieldErrors((prev) => ({ ...prev, [name]: err || undefined }));
  };

  const passwordStrength = getPasswordStrength(formData.password);

  const getFieldClass = (fieldName: string) => {
    const hasError = touched[fieldName] && fieldErrors[fieldName as keyof FieldErrors];
    return `input-base ${hasError ? "border-red-400 focus:border-red-500 focus:ring-red-200" : ""}`;
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center py-12">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-claude-dark mb-3">
            注册
          </h1>
          <p className="text-claude-brown">
            开始你的 AI 小说创作之旅
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-claude-border p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <p className="text-sm">{error}</p>
              </div>
            )}

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-claude-dark mb-2">
                用户名 *
              </label>
              <input
                id="username"
                name="username"
                type="text"
                required
                value={formData.username}
                onChange={handleChange}
                onBlur={handleBlur}
                className={getFieldClass("username")}
                placeholder="3-50 个字符，仅限字母、数字、下划线"
              />
              {touched.username && fieldErrors.username && (
                <p className="mt-1 text-sm text-red-500">{fieldErrors.username}</p>
              )}
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-claude-dark mb-2">
                邮箱 *
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={formData.email}
                onChange={handleChange}
                onBlur={handleBlur}
                className={getFieldClass("email")}
                placeholder="your@email.com"
              />
              {touched.email && fieldErrors.email && (
                <p className="mt-1 text-sm text-red-500">{fieldErrors.email}</p>
              )}
            </div>

            <div>
              <label htmlFor="full_name" className="block text-sm font-medium text-claude-dark mb-2">
                姓名（可选）
              </label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                value={formData.full_name}
                onChange={handleChange}
                className="input-base"
                placeholder="请输入姓名"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-claude-dark mb-2">
                密码 *
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={formData.password}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  className={getFieldClass("password")}
                  placeholder="8-72 个字符"
                  maxLength={72}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-sm text-claude-brown hover:text-claude-dark"
                >
                  {showPassword ? "隐藏" : "显示"}
                </button>
              </div>
              {touched.password && fieldErrors.password && (
                <p className="mt-1 text-sm text-red-500">{fieldErrors.password}</p>
              )}
              {formData.password && !fieldErrors.password && (
                <div className="mt-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${passwordStrength.color}`}
                        style={{ width: `${passwordStrength.level * 25}%` }}
                      />
                    </div>
                    <span className="text-xs text-claude-brown">密码强度：{passwordStrength.label}</span>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-claude-dark mb-2">
                确认密码 *
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type={showPassword ? "text" : "password"}
                required
                value={formData.confirmPassword}
                onChange={handleChange}
                onBlur={handleBlur}
                className={getFieldClass("confirmPassword")}
                placeholder="再次输入密码"
                maxLength={72}
              />
              {touched.confirmPassword && fieldErrors.confirmPassword && (
                <p className="mt-1 text-sm text-red-500">{fieldErrors.confirmPassword}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? "注册中..." : "注册"}
            </button>

            <div className="text-center pt-4">
              <span className="text-sm text-claude-brown">已有账号？</span>
              <a
                href="/login"
                className="ml-1 text-sm font-medium text-claude-dark hover:text-claude-brown"
              >
                立即登录
              </a>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
