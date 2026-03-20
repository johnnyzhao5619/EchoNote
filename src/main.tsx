import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/globals.css";
import "./styles/themes/tokyo-night.css";
import "./styles/themes/tokyo-night-storm.css";
import "./styles/themes/tokyo-night-light.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
