import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

export default function SetupProfile() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    study_hours_per_day: "",
    exam_days_left: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const updateForm = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    setError("");

    try {
      setLoading(true);

      const response = await API.post("/auth/setup-profile", {
        study_hours_per_day: Number(form.study_hours_per_day),
        exam_days_left: Number(form.exam_days_left),
      });

      localStorage.setItem("trackmate_student", JSON.stringify(response.data.student));

      navigate("/dashboard");
    } catch (err) {
      const detail = err?.response?.data?.detail || "Profile setup failed";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={saveProfile}>
        <p className="eyebrow">One Time Setup</p>
        <h1>Study Details</h1>

        <p className="auth-note">
          We ask this only once. From next login, TrackMate will directly open
          your dashboard.
        </p>

        {error && <div className="error-box">{error}</div>}

        <label>How many hours do you study per day?</label>
        <input
          type="number"
          min="0.5"
          max="16"
          step="0.5"
          value={form.study_hours_per_day}
          onChange={(e) => updateForm("study_hours_per_day", e.target.value)}
          placeholder="Example: 3"
          required
        />

        <label>How many days are left for your exam?</label>
        <input
          type="number"
          min="1"
          max="365"
          value={form.exam_days_left}
          onChange={(e) => updateForm("exam_days_left", e.target.value)}
          placeholder="Example: 45"
          required
        />

        <button className="primary-btn full" disabled={loading}>
          {loading ? "Saving..." : "Save & Continue"}
        </button>
      </form>
    </div>
  );
}