import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

export default function OtpPage() {
  const navigate = useNavigate();

  const email = localStorage.getItem("trackmate_login_email") || "";

  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const verifyOtp = async (e) => {
    e.preventDefault();
    setError("");

    try {
      setLoading(true);

      const response = await API.post("/auth/verify-otp", {
        email,
        otp,
      });

      localStorage.setItem("trackmate_token", response.data.access_token);
      localStorage.setItem("trackmate_student", JSON.stringify(response.data.student));

      if (!response.data.profile_completed) {
        navigate("/setup-profile");
      } else {
        navigate("/dashboard");
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || "OTP verification failed";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={verifyOtp}>
        <p className="eyebrow">Email Verification</p>
        <h1>Enter OTP</h1>

        <p className="auth-note">
          OTP sent to <b>{email}</b>. If email setup is not configured, check
          FastAPI backend terminal.
        </p>

        {error && <div className="error-box">{error}</div>}

        <label>OTP</label>
        <input
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
          placeholder="Enter 6 digit OTP"
          maxLength="6"
          required
        />

        <button className="primary-btn full" disabled={loading}>
          {loading ? "Verifying..." : "Verify OTP"}
        </button>
      </form>
    </div>
  );
}