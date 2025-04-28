import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import Layout from "./Layout";

import { BrowserRouter } from "react-router-dom";
import { getUserInfo, checkAuthEnforced } from "../../api/api";
import { before } from "lodash";
import { hostname } from "os";

const DefaultLayoutProps = {
  children: <div> Layout Children </div>,
  toggleSpinner: true,
  onSetShowHistoryPanel: jest.fn(),
  showHistoryBtn: true,
  showHistoryPanel: true,
};

const DefaultLayoutPropsloderfalse = {
    children: <div> Layout Children </div>,
    toggleSpinner: false,
    onSetShowHistoryPanel: jest.fn(),
    showHistoryBtn: true,
    showHistoryPanel: false,
  };

jest.mock('../../api/api', () => ({
    getUserInfo: jest.fn(), checkAuthEnforced: jest.fn()
}));


describe("Layout Component", () => {
  beforeAll(() => {
    // Mocking navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockImplementation(() => Promise.resolve()),
      },
    });
  });



  /*
   commented test case due to chat history feature code merging
  test("renders Layout component", () => {
    render(
      <BrowserRouter>
        <Layout {...DefaultLayoutProps} />
      </BrowserRouter>
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();

    expect(screen.getByAltText("Azure AI logo")).toBeInTheDocument();

    expect(screen.getByText("Azure AI")).toBeInTheDocument();

    expect(screen.getByLabelText("Share")).toBeInTheDocument();
  });
  */

  test('test the auth branching auth is true case', async () => {
    const mocklist: any[] = [];
    Object.defineProperty(window, "location", {
      value: {
          hostname: "NonDeloyed"
      },
  });
    ;(getUserInfo as jest.Mock).mockResolvedValue(mocklist)
    ;(checkAuthEnforced as jest.Mock).mockResolvedValue(true)
    await act(async () => {
        render(
          <BrowserRouter>
            <Layout {...DefaultLayoutPropsloderfalse} />
          </BrowserRouter>
        );
      });
    expect(screen.getByText(/authentication not configured/i)).toBeInTheDocument();
  });

  test('test the auth branching auth is false case', async () => {
    const mocklist: any[] = [1,2,3];
    ;(getUserInfo as jest.Mock).mockResolvedValue(mocklist)
    await act(async () => {
        render(
          <BrowserRouter>
            <Layout {...DefaultLayoutPropsloderfalse} />
          </BrowserRouter>
        );
      });

    expect(screen.getByText(/Show chat history/i)).toBeInTheDocument();
  });

  test("opens share panel", async () => {
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

    const sharebtn = screen.getByLabelText("Share");

    fireEvent.keyDown(sharebtn, { key: "Enter", code: "Enter", charCode: 13 });

    const dialog = screen.getByText("Share the web app");

    expect(dialog).toBeInTheDocument();
  });

  test("opens share panel on other key", async () => {
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

    const sharebtn = screen.getByLabelText("Share");

    fireEvent.keyDown(sharebtn, { key: "A", code: "A", charCode: 65 });

    await waitFor(() => {
      expect(screen.queryByText("Share the web app")).not.toBeInTheDocument();
    });
  });

  test("closes share panel", async () => {
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

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
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

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
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

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

  test("copies URL to clipboard on space key", async () => {
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    const copyButton = screen.getByLabelText("Copy");

    fireEvent.keyDown(copyButton, { key: ' ' });

    // Wait for the state update

    await screen.findByText("Copied URL");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      window.location.href
    );

    expect(screen.getByText("Copied URL")).toBeInTheDocument();
  });

  test("copies URL to clipboard on A key", async () => {
    await act(async () => {
      render(
        <BrowserRouter>
          <Layout {...DefaultLayoutProps} />
        </BrowserRouter>
      );
    });

    const shareButton = screen.getByLabelText("Share");

    fireEvent.click(shareButton);

    const copyButton = screen.getByLabelText("Copy");

    fireEvent.keyDown(copyButton, { key: "A" });

    // Wait for the state update

    await screen.findByText("Copy URL");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      window.location.href
    );

    expect(screen.getByText("Copy URL")).toBeInTheDocument();
  });
});
