import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { THEMES } from "../themes/palettes";
import { ThemeProvider } from "../themes/ThemeContext";
import { ThemePicker } from "./ThemePicker";

function Harness() {
  const [open, setOpen] = useState(true);
  return (
    <I18nProvider>
      <ThemeProvider>
        <button type="button" onClick={() => setOpen(true)}>
          open
        </button>
        {open ? <ThemePicker onClose={() => setOpen(false)} /> : null}
      </ThemeProvider>
    </I18nProvider>
  );
}

const bg = () => document.documentElement.style.getPropertyValue("--bg");
const palette = (id: string) => THEMES.find((theme) => theme.id === id)?.palette;

function setup(theme = "tokyo-night") {
  localStorage.setItem("sdd.lang", "en");
  localStorage.setItem("sdd.theme", theme);
  render(<Harness />);
  return userEvent.setup();
}

describe("ThemePicker", () => {
  it("focuses the current theme and previews whatever gets focus", async () => {
    const user = setup();
    expect(screen.getByRole("option", { name: "Tokyo Night" })).toHaveFocus();
    expect(bg()).toBe(palette("tokyo-night")?.bg);

    await user.hover(screen.getByRole("option", { name: "Nord" }));
    expect(bg()).toBe(palette("nord")?.bg);
  });

  it("reverts the preview on Escape and keeps the saved theme", async () => {
    const user = setup();
    act(() => screen.getByRole("option", { name: "Dracula" }).focus());
    expect(bg()).toBe(palette("dracula")?.bg);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(bg()).toBe(palette("tokyo-night")?.bg);
    expect(localStorage.getItem("sdd.theme")).toBe("tokyo-night");
    expect(document.body.style.overflow).toBe("");
  });

  it("saves the chosen theme", async () => {
    const user = setup();
    await user.click(screen.getByRole("option", { name: "Gruvbox Material" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem("sdd.theme")).toBe("gruvbox-material");
    expect(bg()).toBe(palette("gruvbox-material")?.bg);
  });

  it("filters themes by name and scheme", async () => {
    const user = setup();
    await user.type(screen.getByRole("searchbox"), "light");
    const names = screen.getAllByRole("option").map((option) => option.textContent);
    expect(names.length).toBe(THEMES.filter((theme) => theme.scheme === "light").length);

    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.queryAllByRole("option")).toEqual([]);
    expect(screen.getByText("nothing matches")).toBeInTheDocument();
  });

  it("keeps Tab inside the dialog", async () => {
    const user = setup();
    act(() => screen.getByRole("searchbox").focus());
    await user.tab({ shift: true });
    expect(screen.getByRole("dialog")).toContainElement(document.activeElement as HTMLElement);
  });
});
