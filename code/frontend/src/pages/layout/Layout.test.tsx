import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Layout from "./Layout";

import { BrowserRouter } from "react-router-dom";

describe("Layout Component", () => {
  beforeAll(() => {
    // Mocking navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockImplementation(() => Promise.resolve()),
      },
    });
  });

  test("renders Layout component", () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();

    expect(screen.getByAltText("Azure AI logo")).toBeInTheDocument();

    expect(screen.getByText("Azure AI")).toBeInTheDocument();

    expect(screen.getByLabelText("Share")).toBeInTheDocument();
  });

  test("opens share panel", () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const sharebtn = screen.getByLabelText("Share");

    fireEvent.keyDown(sharebtn, { key: "Enter", code: "Enter", charCode: 13 });

    const dialog = screen.getByText("Share the web app");

    expect(dialog).toBeInTheDocument();
  });

  test("opens share panel on other key", async () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const sharebtn = screen.getByLabelText("Share");

    fireEvent.keyDown(sharebtn, { key: "A", code: "A", charCode: 65 });

    await waitFor(() => {
      expect(screen.queryByText("Share the web app")).not.toBeInTheDocument();
    });
  });

  test("closes share panel", async () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    expect(screen.getByText("Share the web app")).toBeInTheDocument();

    const closeButton = screen.getByRole("button", { name: /close/i });

    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText("Share the web app")).not.toBeInTheDocument();
    });
  });

  test("copies URL to clipboard", async () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    const copyButton = screen.getByLabelText("Copy");

    fireEvent.click(copyButton);

    // Wait for the state update

    await screen.findByText("Copied URL");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      window.location.href
    );

    expect(screen.getByText("Copied URL")).toBeInTheDocument();
  });

  test("copies URL to clipboard on enter key", async () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    const copyButton = screen.getByLabelText("Copy");

    fireEvent.keyDown(copyButton, {
      key: "Enter",
      code: "Enter",
      charCode: 13,
    });

    // Wait for the state update

    await screen.findByText("Copied URL");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      window.location.href
    );

    expect(screen.getByText("Copied URL")).toBeInTheDocument();
  });

  test("copies URL to clipboard on other key", async () => {
    render(
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    );

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    const copyButton = screen.getByLabelText("Copy");

    fireEvent.keyDown(copyButton, { key: "a", code: "KeyA" });

    // Wait for the state update

    await waitFor(() => {
      expect(screen.getByText("Copy URL")).toBeInTheDocument();
    });
  });
});
