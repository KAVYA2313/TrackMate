import { useEffect, useMemo, useState } from "react";
import API from "../api/api";

export default function HistoryPage() {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchHistory = async () => {
    try {
      setLoading(true);
      setError("");

      const res = await API.get("/history/dashboard");
      setHistory(res.data);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to load history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const summary = history?.summary || {};
  const tests = history?.tests || [];
  const trend = history?.trend || [];
  const distribution = history?.distribution || {};
  const chapterPerformance = history?.chapter_performance || [];
  const recommendation = history?.recommendation || {};

  const topChapter = useMemo(() => {
    if (!chapterPerformance.length) return null;

    return [...chapterPerformance].sort(
      (a, b) => b.average_percentage - a.average_percentage
    )[0];
  }, [chapterPerformance]);

  const weakChapter = useMemo(() => {
    if (!chapterPerformance.length) return null;

    return [...chapterPerformance].sort(
      (a, b) => a.average_percentage - b.average_percentage
    )[0];
  }, [chapterPerformance]);

  if (loading) {
    return (
      <div className="history-page">
        <div className="history-loader">
          Loading performance history...
        </div>
      </div>
    );
  }

  return (
    <div className="history-page">
      <div className="history-hero">
        <div>
          <p className="history-kicker">Performance Analytics</p>
          <h1>Test History</h1>
          <p>
            Track every test attempt, marks, chapter-wise score, retention trend,
            and weak chapter performance in one clean dashboard.
          </p>
        </div>

        <div className="history-hero-card">
          <span>Latest Score</span>
          <strong>{summary.latest_percentage || 0}%</strong>
          <small>
            {summary.latest_test_id
              ? `Test #${summary.latest_test_id}`
              : "No test yet"}
          </small>
        </div>
      </div>

      {error && <div className="history-error">{error}</div>}

      <div className="history-stat-grid">
        <HistoryStat
          label="Total Tests"
          value={summary.total_tests || 0}
          note="Submitted attempts"
        />

        <HistoryStat
          label="Average Score"
          value={`${summary.average_percentage || 0}%`}
          note="Overall performance"
        />

        <HistoryStat
          label="Best Score"
          value={`${summary.best_percentage || 0}%`}
          note={
            summary.best_test_id
              ? `Best in Test #${summary.best_test_id}`
              : "No best score yet"
          }
        />

        <HistoryStat
          label="Total Questions"
          value={summary.total_questions || 0}
          note={`${summary.total_obtained_marks || 0}/${summary.total_marks || 0} marks`}
        />
      </div>

      {tests.length === 0 ? (
        <div className="history-empty">
          <h2>No test history found</h2>
          <p>
            Give your first chapter-wise test. After submission, your marks,
            percentage, chapter performance, and charts will appear here.
          </p>
        </div>
      ) : (
        <>
          <div className="history-grid">
            <div className="history-panel large">
              <div className="history-panel-head">
                <div>
                  <h2>Performance Trend</h2>
                  <p>Your percentage score across all submitted tests.</p>
                </div>
              </div>

              <ProgressLineChart trend={trend} />
            </div>

            <div className="history-panel">
              <div className="history-panel-head">
                <div>
                  <h2>Result Split</h2>
                  <p>Strong, average, and weak test attempts.</p>
                </div>
              </div>

              <ResultPie distribution={distribution} />
            </div>
          </div>

          <div className="history-grid">
            <div className="history-panel">
              <div className="history-panel-head">
                <div>
                  <h2>AI Suggestion</h2>
                  <p>Based on your marks and retention.</p>
                </div>
              </div>

              <div className={`history-ai-card ${recommendation.type || "info"}`}>
                <span>{recommendation.type || "info"}</span>
                <h3>{recommendation.title || "Keep Learning"}</h3>
                <p>
                  {recommendation.message ||
                    "Continue taking tests so TrackMate can detect your weak chapters."}
                </p>
              </div>
            </div>

            <div className="history-panel">
              <div className="history-panel-head">
                <div>
                  <h2>Quick Insights</h2>
                  <p>Your strongest and weakest chapter.</p>
                </div>
              </div>

              <div className="history-insight-list">
                <InsightCard
                  label="Strongest Chapter"
                  title={topChapter?.chapter_name || "Not available"}
                  value={
                    topChapter
                      ? `${topChapter.average_percentage}% average`
                      : "No data"
                  }
                  type="good"
                />

                <InsightCard
                  label="Needs Focus"
                  title={weakChapter?.chapter_name || "Not available"}
                  value={
                    weakChapter
                      ? `${weakChapter.average_percentage}% average`
                      : "No data"
                  }
                  type="bad"
                />
              </div>
            </div>
          </div>

          <div className="history-panel chapter-panel">
            <div className="history-panel-head">
              <div>
                <h2>Chapter-wise Performance</h2>
                <p>
                  Chapter attempts, average score, retention, and weak chapter status.
                </p>
              </div>
            </div>

            <ChapterBars chapters={chapterPerformance} />
          </div>

          <div className="history-panel">
            <div className="history-panel-head">
              <div>
                <h2>All Test Attempts</h2>
                <p>Every submitted test with marks, percentage, and chapters.</p>
              </div>
            </div>

            <div className="history-table-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Test</th>
                    <th>Date</th>
                    <th>Subject</th>
                    <th>Chapters</th>
                    <th>Marks</th>
                    <th>Percentage</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>
                  {tests.map((test) => (
                    <tr key={test.id}>
                      <td>
                        <strong>Test #{test.id}</strong>
                      </td>

                      <td>{test.date_label || "-"}</td>

                      <td>{test.subject_name || "Maths"}</td>

                      <td>
                        <div className="history-chip-list">
                          {(test.chapters || []).map((chapter) => (
                            <span key={`${test.id}-${chapter.chapter_id}`}>
                              {chapter.chapter_name}
                            </span>
                          ))}
                        </div>
                      </td>

                      <td>
                        <strong>
                          {test.obtained_marks}/{test.total_marks}
                        </strong>
                      </td>

                      <td>
                        <div className="percent-cell">
                          <span>{test.percentage}%</span>
                          <div className="mini-bar">
                            <i style={{ width: `${test.percentage}%` }} />
                          </div>
                        </div>
                      </td>

                      <td>
                        <span className={`history-badge ${test.performance_badge}`}>
                          {test.performance_label}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="test-card-grid">
            {tests.map((test) => (
              <TestAttemptCard key={test.id} test={test} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function HistoryStat({ label, value, note }) {
  return (
    <div className="history-stat-card">
      <p>{label}</p>
      <h3>{value}</h3>
      <span>{note}</span>
    </div>
  );
}

function ProgressLineChart({ trend }) {
  if (!trend.length) {
    return (
      <div className="history-chart-empty">
        No chart data available yet.
      </div>
    );
  }

  const width = 640;
  const height = 260;
  const paddingX = 34;
  const paddingY = 28;

  const points = trend.map((item, index) => {
    const x =
      trend.length === 1
        ? width / 2
        : paddingX +
          (index * (width - paddingX * 2)) / (trend.length - 1);

    const y =
      height -
      paddingY -
      ((item.percentage || 0) / 100) * (height - paddingY * 2);

    return {
      x,
      y,
      percentage: item.percentage || 0,
      label: item.label,
      date: item.date,
    };
  });

  const polylinePoints = points
    .map((point) => `${point.x},${point.y}`)
    .join(" ");

  return (
    <div className="history-line-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <line x1="34" y1="42" x2="606" y2="42" className="chart-grid-line" />
        <line x1="34" y1="104" x2="606" y2="104" className="chart-grid-line" />
        <line x1="34" y1="166" x2="606" y2="166" className="chart-grid-line" />
        <line x1="34" y1="228" x2="606" y2="228" className="chart-grid-line" />

        <polyline points={polylinePoints} className="chart-line" />

        {points.map((point, index) => (
          <g key={`${point.label}-${index}`}>
            <circle cx={point.x} cy={point.y} r="7" className="chart-dot" />
            <text x={point.x} y={point.y - 14} className="chart-text">
              {point.percentage}%
            </text>
          </g>
        ))}
      </svg>

      <div className="chart-label-row">
        {trend.map((item) => (
          <span key={item.test_id}>{item.label}</span>
        ))}
      </div>
    </div>
  );
}

function ResultPie({ distribution }) {
  const total = distribution.total || 0;

  const strong = distribution.strong || 0;
  const average = distribution.average || 0;
  const weak = distribution.weak || 0;

  const strongPercent = total ? Math.round((strong / total) * 100) : 0;
  const averagePercent = total ? Math.round((average / total) * 100) : 0;
  const weakPercent = total ? Math.round((weak / total) * 100) : 0;

  const pieStyle = {
    background: `conic-gradient(
      #16a34a 0 ${strongPercent}%,
      #f59e0b ${strongPercent}% ${strongPercent + averagePercent}%,
      #ef4444 ${strongPercent + averagePercent}% 100%
    )`,
  };

  return (
    <div className="history-pie-wrap">
      <div className="history-pie" style={pieStyle}>
        <div>
          <strong>{total}</strong>
          <span>Tests</span>
        </div>
      </div>

      <div className="history-pie-legend">
        <LegendItem color="good" label="Strong" value={`${strong} tests`} />
        <LegendItem color="warn" label="Average" value={`${average} tests`} />
        <LegendItem color="bad" label="Weak" value={`${weak} tests`} />
      </div>
    </div>
  );
}

function LegendItem({ color, label, value }) {
  return (
    <div className="history-legend-item">
      <i className={color} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InsightCard({ label, title, value, type }) {
  return (
    <div className={`history-insight-card ${type}`}>
      <span>{label}</span>
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  );
}

function ChapterBars({ chapters }) {
  if (!chapters.length) {
    return (
      <div className="history-chart-empty">
        No chapter performance available yet.
      </div>
    );
  }

  return (
    <div className="chapter-bar-list">
      {chapters.map((chapter) => (
        <div className="chapter-bar-row" key={chapter.chapter_id}>
          <div className="chapter-bar-info">
            <strong>{chapter.chapter_name}</strong>
            <span>
              {chapter.attempt_count} attempt
              {chapter.attempt_count > 1 ? "s" : ""} • Retention{" "}
              {chapter.retention || 0}% • Priority {chapter.priority_score || 0}
            </span>
          </div>

          <div className="chapter-bar-track">
            <i style={{ width: `${chapter.average_percentage}%` }} />
          </div>

          <div className="chapter-score">
            {chapter.average_percentage}%
          </div>

          <span className={`history-badge ${chapter.badge}`}>
            {chapter.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function TestAttemptCard({ test }) {
  return (
    <div className="test-attempt-card">
      <div className="test-attempt-top">
        <div>
          <span>Test #{test.id}</span>
          <h3>{test.subject_name || "Maths"}</h3>
        </div>

        <strong>{test.percentage}%</strong>
      </div>

      <div className="test-attempt-meta">
        <span>{test.date_label || "-"}</span>
        <span>
          {test.obtained_marks}/{test.total_marks} marks
        </span>
        <span>{test.total_questions} questions</span>
      </div>

      <div className="test-attempt-chapters">
        {(test.chapters || []).map((chapter) => (
          <div key={`${test.id}-${chapter.chapter_id}`}>
            <p>{chapter.chapter_name}</p>
            <span>
              {chapter.obtained_marks}/{chapter.total_questions} •{" "}
              {chapter.percentage}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}