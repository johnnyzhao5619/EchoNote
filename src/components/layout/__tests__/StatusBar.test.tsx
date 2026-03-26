import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBar } from "../StatusBar";
import { useRecordingStore } from "@/store/recording";

describe("StatusBar", () => {
  beforeEach(() => {
    useRecordingStore.setState({
      status: "idle",
      sessionId: null,
      startedAt: null,
      audioLevel: 0,
      segments: [],
      devices: [],
      devicesLoading: false,
      _unlisteners: [],
      _levelTimer: null,
    });
  });

  it("renders version text", () => {
    render(<StatusBar />);
    expect(screen.getByText("EchoNote v3.0.0")).toBeInTheDocument();
  });

  it("uses semantic theme classes for recording indicator and bars", () => {
    useRecordingStore.setState({
      status: "recording",
      audioLevel: 0.5,
    });

    render(<StatusBar />);

    expect(screen.getByTestId("recording-dot")).toHaveClass("bg-status-error");
    expect(screen.getByTestId("audio-level-bar-0")).toHaveClass("bg-status-success");
    expect(screen.getByTestId("audio-level-bar-7")).toHaveClass("bg-border-default");
  });
});
