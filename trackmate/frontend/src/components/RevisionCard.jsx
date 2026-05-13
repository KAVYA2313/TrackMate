export default function RevisionCard({ data }) {
  const plan = data?.plan || {};
  const topic = data?.topic || {};

  return (
    <div className="revision-card">
      <div className="revision-card-head">
        <span>AI Micro Revision</span>
        <h2>{plan.title || `Revise ${topic.topic_name || "Topic"}`}</h2>
        <p>{plan.why_this_topic || "This topic needs focused revision."}</p>
      </div>

      <RevisionList title="Concept Recap" items={plan.concept_recap || []} />
      <RevisionList title="Common Mistakes" items={plan.common_mistakes || []} />
      <RevisionList title="Practice Tasks" items={plan.practice_tasks || []} />

      <div className="revision-mini-plan">
        <h3>Mini Plan</h3>
        {(plan.mini_plan || []).map((item, index) => (
          <div key={index} className="revision-mini-row">
            <strong>{item.minutes} min</strong>
            <span>{item.activity}</span>
          </div>
        ))}
      </div>

      <div className="revision-retest">
        {plan.retest_advice || "After revision, take a short test."}
      </div>
    </div>
  );
}

function RevisionList({ title, items }) {
  return (
    <div className="revision-list">
      <h3>{title}</h3>

      {items.length === 0 ? (
        <p>No points generated.</p>
      ) : (
        <ul>
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}