import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

function GenerateTest() {
  const navigate = useNavigate();

  const [chapters, setChapters] = useState([]);
  const [selectedChapters, setSelectedChapters] = useState([]);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState("Easy");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const studentId = 1;
  const subjectId = 1;

  useEffect(() => {
    fetchChapters();
  }, []);

  const fetchChapters = async () => {
    try {
      const response = await API.get(`/chapters/subject/${subjectId}`);
      setChapters(response.data);
    } catch (err) {
      console.error("Chapter fetch failed:", err);
      setError("Failed to load chapters.");
    }
  };

  const toggleChapter = (chapterId) => {
    setSelectedChapters((prev) => {
      if (prev.includes(chapterId)) {
        return prev.filter((id) => id !== chapterId);
      }

      return [...prev, chapterId];
    });
  };

  const generateTest = async () => {
    setError("");

    if (selectedChapters.length === 0) {
      setError("Please select at least one chapter.");
      return;
    }

    if (!questionCount || Number(questionCount) <= 0) {
      setError("Please enter valid question count.");
      return;
    }

    try {
      setLoading(true);

      const payload = {
        student_id: studentId,
        subject_id: subjectId,
        chapter_ids: selectedChapters,
        question_count: Number(questionCount),
        difficulty: difficulty,
      };

      const response = await API.post("/tests/generate", payload);

      navigate("/test", {
        state: {
          test: response.data,
        },
      });
    } catch (err) {
      console.error("Generate test failed:", err);

      const detail =
        err?.response?.data?.detail ||
        "Test generation failed. Check backend terminal.";

      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <section className="hero-section">
        <div>
          <p className="eyebrow">Maths Practice Engine</p>
          <h1>Generate Chapter Test</h1>
          <p className="subtitle">
            Select difficulty, chapters, and number of questions. TrackMate will
            generate a smart chapter-wise test.
          </p>
        </div>

        <div className="hero-badge">
          <span>{selectedChapters.length}</span>
          <small>chapters selected</small>
        </div>
      </section>

      <section className="glass-card">
        {error && <div className="error-box">{error}</div>}

        <div className="form-group">
          <label>Difficulty Level</label>

          <div className="difficulty-grid">
            {["Easy", "Medium", "Hard"].map((level) => (
              <button
                type="button"
                key={level}
                className={
                  difficulty === level
                    ? "difficulty-card active"
                    : "difficulty-card"
                }
                onClick={() => setDifficulty(level)}
              >
                <span>{level}</span>
                <small>
                  {level === "Easy" && "Basic concept questions"}
                  {level === "Medium" && "Moderate practice questions"}
                  {level === "Hard" && "Advanced challenge questions"}
                </small>
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>How many questions?</label>
          <input
            type="number"
            min="1"
            value={questionCount}
            onChange={(e) => setQuestionCount(e.target.value)}
            placeholder="Enter question count"
          />
        </div>

        <div className="section-title-row">
          <h2>Select Chapters</h2>
          <p>
            Selected difficulty: <b>{difficulty}</b>
          </p>
        </div>

        <div className="chapter-grid">
          {chapters.map((chapter) => {
            const isSelected = selectedChapters.includes(chapter.id);

            return (
              <button
                type="button"
                key={chapter.id}
                className={isSelected ? "chapter-card selected" : "chapter-card"}
                onClick={() => toggleChapter(chapter.id)}
              >
                <div className="chapter-top">
                  <span className="chapter-number">
                    Chapter {chapter.chapter_order}
                  </span>

                  <span className={isSelected ? "check active" : "check"}>
                    {isSelected ? "✓" : ""}
                  </span>
                </div>

                <h3>{chapter.chapter_name}</h3>
              </button>
            );
          })}
        </div>

        <div className="action-row">
          <button
            className="primary-btn"
            onClick={generateTest}
            disabled={loading}
          >
            {loading ? "Generating..." : `Generate ${difficulty} Test`}
          </button>
        </div>
      </section>
    </div>
  );
}

export default GenerateTest;