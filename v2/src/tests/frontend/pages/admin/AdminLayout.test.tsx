/**
 * Pillar: Stable Core
 * Phase: 5 (Admin + Frontend Merge)
 *
 * Tests for <AdminLayout>: the shared admin chrome. Verifies the
 * secondary nav renders a link per admin page, the active link is
 * marked aria-current, the routed child renders through <Outlet/>,
 * sub-nav clicks switch pages, and the "Back to CWYD" button returns
 * to the chat root.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AdminLayout } from "@/pages/admin/AdminLayout";
import { FluentThemeBridge } from "@/theme/FluentThemeBridge";
import { ThemeProvider } from "@/theme/themeContext";

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <FluentThemeBridge>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route
                path="ingest"
                element={<div data-testid="ingest-child">Ingest</div>}
              />
              <Route
                path="config"
                element={<div data-testid="config-child">Config</div>}
              />
            </Route>
            <Route
              path="/"
              element={<div data-testid="chat-home">Chat home</div>}
            />
          </Routes>
        </MemoryRouter>
      </FluentThemeBridge>
    </ThemeProvider>,
  );
}

describe("AdminLayout", () => {
  it("renders a sub-nav link for each admin page", () => {
    renderAt("/admin/ingest");
    expect(screen.getByTestId("admin-subnav-ingest")).toBeInTheDocument();
    expect(screen.getByTestId("admin-subnav-delete")).toBeInTheDocument();
    expect(screen.getByTestId("admin-subnav-config")).toBeInTheDocument();
    // Regression guard: the standalone Prompt editor page was folded
    // into Configuration, so its sub-nav link no longer renders.
    expect(screen.queryByTestId("admin-subnav-prompt")).not.toBeInTheDocument();
  });

  it("renders the routed admin page through the outlet", () => {
    renderAt("/admin/ingest");
    expect(screen.getByTestId("ingest-child")).toBeInTheDocument();
  });

  it("marks the active page link with aria-current", () => {
    renderAt("/admin/ingest");
    expect(screen.getByTestId("admin-subnav-ingest")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByTestId("admin-subnav-config")).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("navigates between admin pages when a sub-nav link is clicked", () => {
    renderAt("/admin/ingest");
    expect(screen.getByTestId("ingest-child")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("admin-subnav-config"));
    expect(screen.getByTestId("config-child")).toBeInTheDocument();
    expect(screen.queryByTestId("ingest-child")).not.toBeInTheDocument();
  });

  it("labels the back-home button 'Back to CWYD'", () => {
    renderAt("/admin/ingest");
    expect(screen.getByTestId("admin-back-home")).toHaveTextContent(
      "Back to CWYD",
    );
  });

  it("returns to the chat root when the back-home button is clicked", () => {
    renderAt("/admin/ingest");
    fireEvent.click(screen.getByTestId("admin-back-home"));
    expect(screen.getByTestId("chat-home")).toBeInTheDocument();
    expect(screen.queryByTestId("admin-layout")).not.toBeInTheDocument();
  });
});
