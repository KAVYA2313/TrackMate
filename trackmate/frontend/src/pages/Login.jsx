import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import API from "../api/api";
import Toast from "../components/Toast";

export default function Login() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    email: "",
    password: "",
  });

  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (type, title, message) => {
    setToast({
      type,
      title,
      message,
      duration: 2500,
    });
  };

  const handleChange = (e) => {
    setForm((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.email.trim() || !form.password.trim()) {
      showToast("error", "Missing Details", "Please enter email and password.");
      return;
    }

    try {
      setLoading(true);

      await API.post("/auth/login", {
        email: form.email.trim(),
        password: form.password,
      });

      localStorage.setItem("trackmate_login_email", form.email.trim());

      showToast(
        "success",
        "OTP Sent",
        "Check your email or backend terminal for the OTP."
      );

      setTimeout(() => {
        navigate("/otp");
      }, 900);
    } catch (error) {
      console.error(error);

      showToast(
        "error",
        "Login Failed",
        error?.response?.data?.detail || "Invalid email or password."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="auth-card auth-card-premium">
        <p className="eyebrow">Secure Login</p>

        <h1>Login</h1>

        <p className="auth-note">
          Enter your email and password. We will send an OTP for secure access.
        </p>

        <form onSubmit={handleSubmit}>
          <label>Email</label>
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            placeholder="Enter your email"
            autoComplete="email"
          />

          <label>Password</label>
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={handleChange}
            placeholder="Enter your password"
            autoComplete="current-password"
          />

          <button className="primary-btn full" disabled={loading}>
            {loading ? "Sending OTP..." : "Send OTP"}
          </button>
        </form>

        <p className="auth-switch">
          New student? <Link to="/signup">Signup</Link>
        </p>
      </div>
    </div>
  );
}