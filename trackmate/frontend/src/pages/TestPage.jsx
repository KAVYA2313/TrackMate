import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import API from "../api/api.js";

export default function TestPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const stateTest = location.state?.test || null;

  const savedTest = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("trackmate_test") || "null");
    } catch {
      return null;
    }
  }, []);

  const [test, setTest] = useState(stateTest || savedTest);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (stateTest) {
      setTest(stateTest);
      setAnswers({});
      setError("");

      localStorage.removeItem("trackmate_result");
      localStorage.removeItem("trackmate_answers");
      localStorage.setItem("trackmate_test", JSON.stringify(stateTest));
    }
  }, [stateTest]);

  if (!test) {
    return (
      <div className="empty-state">
        <h1>No test found</h1>
        <p>Generate a test first, then come back here.</p>
        <button className="btn primary" onClick={() => navigate("/generate-test")}>
          Generate Test
        </button>
      </div>
    );
  }

  const totalQuestions = test.questions?.length || 0;
  const answeredCount = Object.keys(answers).length;
  const progressPercent = totalQuestions
    ? Math.round((answeredCount / totalQuestions) * 100)
    : 0;

  const selectedChaptersText =
    test.selected_chapters?.join(", ") || "Selected chapters";

  const submit = async () => {
    setError("");

    if (answeredCount !== totalQuestions) {
      setError(
        `Please answer all questions before submit. Answered ${answeredCount}/${totalQuestions}.`
      );
      return;
    }

    setLoading(true);

    try {
      const payload = {
        answers: test.questions.map((question) => ({
          question_id: Number(question.question_id),
          selected_answer: answers[question.question_id],
        })),
      };

      console.log("Submit payload:", payload);

      const res = await API.post(`/tests/${test.test_id}/submit`, payload);

      localStorage.setItem("trackmate_result", JSON.stringify(res.data));
      navigate("/result");
    } catch (err) {
      console.error("Submit error:", err.response?.data || err.message);

      const detail = err.response?.data?.detail;

      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
      } else {
        setError("Submit failed. Check FastAPI terminal for exact backend error.");
      }
    } finally {
      setLoading(false);
    }
  };

  const clearAndGenerateAgain = () => {
    localStorage.removeItem("trackmate_test");
    localStorage.removeItem("trackmate_result");
    localStorage.removeItem("trackmate_answers");
    navigate("/generate-test");
  };

  return (
    <div className="test-layout">
      <div className="page-hero compact">
        <div>
          <p className="eyebrow">Maths assessment</p>
          <h1>Chapter Test #{test.test_id}</h1>
          <p className="muted">
            Difficulty: <b>{test.difficulty}</b> · Chapters:{" "}
            <b>{selectedChaptersText}</b> · Questions:{" "}
            <b>{totalQuestions}</b>
          </p>
        </div>

        <div className="score-ring">
          <span>{progressPercent}%</span>
          <small>
            {answeredCount}/{totalQuestions}
          </small>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="test-debug-card">
        <strong>Current generated test:</strong>
        <span>Difficulty: {test.difficulty}</span>
        <span>Selected chapters: {selectedChaptersText}</span>
        <span>Total questions: {totalQuestions}</span>
      </div>

      <div className="question-list">
        {test.questions.map((q, index) => (
          <div className="question-card" key={q.question_id}>
            <div className="question-topline">
              <span className="question-number">Q{index + 1}</span>

              <span className="badge">
                Chapter {q.chapter_order || q.chapter_id}
              </span>

              {q.chapter_name && (
                <span className="badge soft">{q.chapter_name}</span>
              )}

              <span className="badge soft">{q.difficulty || test.difficulty}</span>
            </div>

            <h3>{q.question_text}</h3>

            <div className="options-grid">
              {["A", "B", "C", "D"].map((opt) => {
                const selected = answers[q.question_id] === opt;

                return (
                  <label
                    key={opt}
                    className={`option-card ${selected ? "selected" : ""}`}
                  >
                    <input
                      type="radio"
                      name={`q-${q.question_id}`}
                      value={opt}
                      checked={selected}
                      onChange={() =>
                        setAnswers((prev) => ({
                          ...prev,
                          [q.question_id]: opt,
                        }))
                      }
                    />
                    <span className="option-letter">{opt}</span>
                    <span>{q[`option_${opt.toLowerCase()}`]}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="submit-bar">
        <div>
          <strong>
            {answeredCount}/{totalQuestions}
          </strong>{" "}
          questions answered
          <p className="muted small">
            All questions are required for correct scoring.
          </p>
        </div>

        <div style={{ display: "flex", gap: "12px" }}>
          <button className="btn ghost" onClick={clearAndGenerateAgain}>
            Generate Again
          </button>

          <button className="btn primary" onClick={submit} disabled={loading}>
            {loading ? "Submitting..." : "Submit Test"}
          </button>
        </div>
      </div>
    </div>
  );
}