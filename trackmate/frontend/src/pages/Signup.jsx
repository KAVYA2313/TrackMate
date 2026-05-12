import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import API from "../api/api";

export default function Signup() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const updateForm = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const signup = async (e) => {
    e.preventDefault();
    setError("");

    try {
      setLoading(true);
      await API.post("/auth/signup", form);
      alert("Signup successful. Please login.");
      navigate("/login");
    } catch (err) {
      setError(err?.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={signup}>
        <p className="eyebrow">Create Account</p>
        <h1>Signup</h1>

        {error && <div className="error-box">{error}</div>}

        <label>Name</label>
        <input
          value={form.name}
          onChange={(e) => updateForm("name", e.target.value)}
          placeholder="Enter your name"
          required
        />

        <label>Email</label>
        <input
          type="email"
          value={form.email}
          onChange={(e) => updateForm("email", e.target.value)}
          placeholder="Enter email"
          required
        />

        <label>Password</label>
        <input
          type="password"
          value={form.password}
          onChange={(e) => updateForm("password", e.target.value)}
          placeholder="Minimum 6 characters"
          required
        />

        <button className="primary-btn full" disabled={loading}>
          {loading ? "Creating..." : "Create Account"}
        </button>

        <p className="auth-switch">
          Already have account? <Link to="/login">Login</Link>
        </p>
      </form>
    </div>
  );
}