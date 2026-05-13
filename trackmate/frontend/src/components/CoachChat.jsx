import { useState } from "react";
import API from "../api/api";

export default function CoachChat() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hi! Ask me what to study today, why a topic is scheduled, or how to improve.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const quickQuestions = [
    "What should I study today?",
    "I have only 30 minutes, what should I do?",
    "Why is this chapter important?",
    "How can I improve after a low score?",
  ];

  const sendMessage = async (textValue = input) => {
    const text = String(textValue || "").trim();

    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");

    try {
      setLoading(true);

      const res = await API.post("/coach/ask", {
        message: text,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: res.data.answer,
          aiUsed: res.data.ai_used,
        },
      ]);
    } catch (err) {
      console.error(err);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, I could not answer right now. Start with today's scheduled revision task.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="coach-chat">
      <div className="coach-chat-head">
        <span>AI Study Coach</span>
        <h2>Ask TrackMate</h2>
        <p>Simple guidance based on your tests, schedule, and weak topics.</p>
      </div>

      <div className="coach-quick-row">
        {quickQuestions.map((question) => (
          <button key={question} onClick={() => sendMessage(question)}>
            {question}
          </button>
        ))}
      </div>

      <div className="coach-message-box">
        {messages.map((msg, index) => (
          <div key={index} className={`coach-message ${msg.role}`}>
            <p>{msg.text}</p>
          </div>
        ))}

        {loading && (
          <div className="coach-message assistant">
            <p>Thinking...</p>
          </div>
        )}
      </div>

      <div className="coach-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your study question..."
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              sendMessage();
            }
          }}
        />

        <button onClick={() => sendMessage()} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
}