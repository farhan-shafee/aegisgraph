import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "./theme-toggle";
afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
describe("theme preference", () => {
  it("switches both ways and persists the selected theme", async () => {
    render(<ThemeToggle />);
    await userEvent.click(
      screen.getByRole("button", { name: "Switch to light theme" }),
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(localStorage.getItem("aegisgraph-theme")).toBe("light");
    await userEvent.click(
      screen.getByRole("button", { name: "Switch to dark theme" }),
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });
  it("loads a saved preference and responds to another tab changing it", () => {
    localStorage.setItem("aegisgraph-theme", "light");
    render(<ThemeToggle />);
    expect(
      screen.getByRole("button", { name: "Switch to dark theme" }),
    ).toBeVisible();
    act(() => {
      localStorage.setItem("aegisgraph-theme", "dark");
      window.dispatchEvent(new Event("storage"));
    });
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });
});
