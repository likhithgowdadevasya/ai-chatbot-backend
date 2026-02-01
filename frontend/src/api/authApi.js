import api from "./axios";

export const loginUser = (data) =>
  api.post("/login", new URLSearchParams(data));

export const signupUser = (data) =>
  api.post("/signup", null, { params: data });
