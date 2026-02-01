import { useState } from "react";
import API from "../services/api";
import { useNavigate } from "react-router-dom";

export default function Signup() {
  const nav = useNavigate();
  const [username,setUsername] = useState("");
  const [password,setPassword] = useState("");

  const signup = async () => {
    try {
      await API.post(`/signup?username=${username}&password=${password}`);
      alert("Signup success");
      nav("/");
    } catch {
      alert("Signup failed");
    }
  };

  return (
    <div className="h-screen flex items-center justify-center">
      <div className="p-6 shadow-xl rounded-xl w-96">
        <h2 className="text-xl font-bold mb-4">Signup</h2>

        <input
          className="border p-2 w-full mb-3"
          placeholder="Username"
          onChange={e=>setUsername(e.target.value)}
        />

        <input
          className="border p-2 w-full mb-3"
          type="password"
          placeholder="Password"
          onChange={e=>setPassword(e.target.value)}
        />

        <button
          className="bg-green-600 text-white w-full p-2 rounded"
          onClick={signup}
        >
          Signup
        </button>
      </div>
    </div>
  );
}
