/**
 * Pillar: Stable Core
 * Phase: 7 (Testing + Documentation)
 *
 * Vitest suite for the admin Delete Data page. Mocks
 * `src/api/admin.tsx` so each scenario (loading / loaded / empty /
 * failed / per-row delete) is asserted against the typed client
 * surface without hitting the network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DeleteData } from "../../../../src/pages/admin/DeleteData/DeleteData";
import {
  deleteDocument,
  listDocuments,
} from "../../../../src/api/admin";
import type {
  DeleteDocumentResponse,
  ListDocumentsResponse,
  SourceListing,
} from "../../../../src/models/admin";

vi.mock("../../../../src/api/admin", () => ({
  listDocuments: vi.fn(),
  deleteDocument: vi.fn(),
}));

const listMock = vi.mocked(listDocuments);
const deleteMock = vi.mocked(deleteDocument);

const ALPHA: SourceListing = {
  source: "alpha.pdf",
  chunk_count: 3,
  last_modified: null,
};
const BETA: SourceListing = {
  source: "beta.pdf",
  chunk_count: 7,
  last_modified: "2026-05-01T12:00:00Z",
};

const LIST_FIXTURE: ListDocumentsResponse = {
  documents: [ALPHA, BETA],
  total: 2,
};

const EMPTY_FIXTURE: ListDocumentsResponse = {
  documents: [],
  total: 0,
};

const DELETE_FIXTURE: DeleteDocumentResponse = {
  deleted: 3,
};

beforeEach(() => {
  listMock.mockReset();
  deleteMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DeleteData -- page shell", () => {
  it("renders the page heading", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);
    expect(
      screen.getByRole("heading", { name: /delete data/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /indexed sources/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(listMock).toHaveBeenCalledTimes(1);
    });
  });
});

describe("DeleteData -- initial list call", () => {
  it("fires listDocuments on mount and renders one row per source", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    expect(listMock).toHaveBeenCalledTimes(1);
    expect(listMock).toHaveBeenCalledWith();
    expect(screen.getByTestId("source-row-alpha.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("source-row-beta.pdf")).toBeInTheDocument();
  });

  it("surfaces chunk_count and last_modified per row", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    const alphaRow = screen.getByTestId("source-row-alpha.pdf");
    expect(alphaRow).toHaveTextContent("alpha.pdf");
    expect(alphaRow).toHaveTextContent("3");
    // null last_modified renders as the em-dash placeholder.
    expect(alphaRow).toHaveTextContent("—");

    const betaRow = screen.getByTestId("source-row-beta.pdf");
    expect(betaRow).toHaveTextContent("beta.pdf");
    expect(betaRow).toHaveTextContent("7");
    expect(betaRow).toHaveTextContent("2026-05-01T12:00:00Z");
  });

  it("shows the loading status before the list call resolves", async () => {
    // Resolve manually so the loading state is observable.
    let resolveList: (value: ListDocumentsResponse) => void = () => {};
    listMock.mockImplementationOnce(
      () =>
        new Promise<ListDocumentsResponse>((resolve) => {
          resolveList = resolve;
        }),
    );
    render(<DeleteData />);

    expect(screen.getByTestId("loading-message")).toBeInTheDocument();
    expect(screen.queryByTestId("source-table")).not.toBeInTheDocument();

    resolveList(LIST_FIXTURE);
    await waitFor(() => {
      expect(screen.queryByTestId("loading-message")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("source-table")).toBeInTheDocument();
  });

  it("shows an explicit empty-state message when the index has no sources", async () => {
    listMock.mockResolvedValueOnce(EMPTY_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-message")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("source-table")).not.toBeInTheDocument();
  });

  it("surfaces an error message and a Retry button when the list call rejects", async () => {
    listMock.mockRejectedValueOnce(
      new Error("listDocuments: request failed with status 503"),
    );
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("list-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("list-error")).toHaveTextContent(/status 503/);
    expect(screen.getByTestId("list-retry")).toBeInTheDocument();
  });

  it("Retry re-fires the list call after a failure", async () => {
    listMock
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("list-retry")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("list-retry"));

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    expect(listMock).toHaveBeenCalledTimes(2);
  });
});

describe("DeleteData -- per-row delete flow", () => {
  it("Delete button opens a confirmation dialog naming the source", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-delete-alpha.pdf"));

    const dialog = screen.getByTestId("delete-confirm-dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveTextContent(/alpha\.pdf/);
    expect(deleteMock).not.toHaveBeenCalled();
  });

  it("Cancel closes the dialog without firing the wire call", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-delete-alpha.pdf"));
    fireEvent.click(screen.getByTestId("delete-cancel"));

    await waitFor(() => {
      expect(
        screen.queryByTestId("delete-confirm-dialog"),
      ).not.toBeInTheDocument();
    });
    expect(deleteMock).not.toHaveBeenCalled();
    // Row should still be present.
    expect(screen.getByTestId("source-row-alpha.pdf")).toBeInTheDocument();
  });

  it("Confirm fires deleteDocument with the source and removes the row on success", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    deleteMock.mockResolvedValueOnce(DELETE_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-delete-alpha.pdf"));
    fireEvent.click(screen.getByTestId("delete-confirm"));

    await waitFor(() => {
      expect(
        screen.queryByTestId("source-row-alpha.pdf"),
      ).not.toBeInTheDocument();
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
    expect(deleteMock).toHaveBeenCalledWith("alpha.pdf");
    // Other rows are unaffected.
    expect(screen.getByTestId("source-row-beta.pdf")).toBeInTheDocument();
  });

  it("surfaces a row-level error and a Retry button when delete rejects", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    deleteMock.mockRejectedValueOnce(
      new Error("deleteDocument: request failed with status 503"),
    );
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-delete-alpha.pdf"));
    fireEvent.click(screen.getByTestId("delete-confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("row-error-alpha.pdf")).toBeInTheDocument();
    });
    expect(screen.getByTestId("row-error-alpha.pdf")).toHaveTextContent(
      /status 503/,
    );
    expect(screen.getByTestId("row-retry-alpha.pdf")).toBeInTheDocument();
    // Row is still rendered (delete did not succeed).
    expect(screen.getByTestId("source-row-alpha.pdf")).toBeInTheDocument();
  });

  it("Retry re-opens the confirm dialog so the operator can re-fire the delete", async () => {
    listMock.mockResolvedValueOnce(LIST_FIXTURE);
    deleteMock
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(DELETE_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-delete-alpha.pdf"));
    fireEvent.click(screen.getByTestId("delete-confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("row-retry-alpha.pdf")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("row-retry-alpha.pdf"));
    expect(screen.getByTestId("delete-confirm-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("delete-confirm"));

    await waitFor(() => {
      expect(
        screen.queryByTestId("source-row-alpha.pdf"),
      ).not.toBeInTheDocument();
    });
    expect(deleteMock).toHaveBeenCalledTimes(2);
  });
});

describe("DeleteData -- refresh", () => {
  it("Refresh button re-fires listDocuments", async () => {
    listMock
      .mockResolvedValueOnce(LIST_FIXTURE)
      .mockResolvedValueOnce(EMPTY_FIXTURE);
    render(<DeleteData />);

    await waitFor(() => {
      expect(screen.getByTestId("source-table")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("empty-message")).toBeInTheDocument();
    });
    expect(listMock).toHaveBeenCalledTimes(2);
  });
});
