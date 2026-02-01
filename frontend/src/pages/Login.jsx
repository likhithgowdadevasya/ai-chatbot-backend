import { useState } from "react";
import API from "../services/api";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const login = async () => {
    try {
      const form = new URLSearchParams();
      form.append("username", username);
      form.append("password", password);

      const res = await API.post("/login", form);

      localStorage.setItem("token", res.data.access_token);
      nav("/chat");

    } catch {
      alert("Login failed");
    }
  };

  return (
    <div className="h-screen flex items-center justify-center">
      <div className="p-6 shadow-xl rounded-xl w-96">
        <h2 className="text-xl font-bold mb-4">Login</h2>

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
          className="bg-blue-600 text-white w-full p-2 rounded"
          onClick={login}
        >
          Login
        </button>

        <p className="mt-3 text-sm">
          New user? <a href="/signup" className="text-blue-600">Signup</a>
        </p>
      </div>
    </div>
  );
}
