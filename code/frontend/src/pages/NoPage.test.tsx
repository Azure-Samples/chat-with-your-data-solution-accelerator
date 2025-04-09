import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import NoPage from "./NoPage";

describe("NoPage.tsx", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders NoPage Component heading", () => {
    render(<NoPage />);
    const headingElement = screen.getByRole("heading");
    expect(headingElement).toBeInTheDocument();
  });

  test("renders NoPage Component with Correct Text", () => {
    render(<NoPage />);
    const ErrorElement = screen.getByText("404");
    expect(ErrorElement.textContent).toEqual("404");
  });

  test("renders NoPage Component heading Level 1", () => {
    render(<NoPage />);
    const headingElement = screen.getByRole("heading", { level: 1 });
    expect(headingElement.tagName).toEqual("H1");
  });
});
