import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SecondPanel } from "../SecondPanel";

describe("SecondPanel", () => {
  it("renders children", () => {
    render(
      <SecondPanel>
        <div data-testid="panel-content">content</div>
      </SecondPanel>
    );
    expect(screen.getByTestId("panel-content")).toBeInTheDocument();
  });

  it("has a resize separator", () => {
    render(
      <SecondPanel>
        <div />
      </SecondPanel>
    );
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });

  it("collapses on double-click when collapsible=true", () => {
    render(
      <SecondPanel collapsible defaultWidth={240}>
        <div data-testid="inner" />
      </SecondPanel>
    );
    const separator = screen.getByRole("separator");
    fireEvent.dblClick(separator);
    // 折叠后 panel 内容变为 aria-hidden
    expect(screen.getByTestId("inner").parentElement)
      .toHaveAttribute("aria-hidden", "true");
  });
});
