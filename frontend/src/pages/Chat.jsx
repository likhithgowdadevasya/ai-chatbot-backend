import { useState } from "react";
import API from "../services/api";

export default function Chat() {
  const [msg,setMsg] = useState("");
  const [reply,setReply] = useState("");

  const send = async () => {
    const res = await API.post("/chat", { message: msg });
    setReply(res.data.bot_reply);
  };

  return (
    <div className="p-10">
      <h2 className="text-2xl font-bold mb-4">Chatbot</h2>

      <input
        className="border p-2 mr-2"
        onChange={e=>setMsg(e.target.value)}
      />

      <button
        className="bg-purple-600 text-white p-2"
        onClick={send}
      >
        Send
      </button>

      <p className="mt-4">Bot: {reply}</p>
    </div>
  );
}
