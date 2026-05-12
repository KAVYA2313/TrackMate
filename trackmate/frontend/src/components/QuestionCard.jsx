export default function QuestionCard({ question }) {
  return (
    <div className="card">
      <h3>{question?.question_text || "Question"}</h3>
      <p>A. {question?.option_a}</p>
      <p>B. {question?.option_b}</p>
      <p>C. {question?.option_c}</p>
      <p>D. {question?.option_d}</p>
    </div>
  );
}
