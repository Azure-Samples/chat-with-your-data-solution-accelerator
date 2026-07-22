/**
 * Vitest suite for the admin Ingest Data page. Mocks
 * `src/api/admin.tsx` so each section's wire interaction is asserted
 * against the typed client surface without hitting the network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { IngestData } from "@/pages/admin/IngestData/IngestData";
import {
  addDocumentUrl,
  reprocessAll,
  uploadDocument,
} from "@/api/admin";
import type {
  IngestUrlResponse,
  ReprocessResponse,
  UploadResponse,
} from "@/models/admin";

vi.mock("@/api/admin", () => ({
  uploadDocument: vi.fn(),
  addDocumentUrl: vi.fn(),
  reprocessAll: vi.fn(),
}));

const uploadMock = vi.mocked(uploadDocument);
const addUrlMock = vi.mocked(addDocumentUrl);
const reprocessMock = vi.mocked(reprocessAll);

const UPLOAD_FIXTURE: UploadResponse = {
  filename: "test.pdf",
  blob_path: "documents/test.pdf",
  ingestion_job_id: "11111111-1111-1111-1111-111111111111",
  queued: true,
};

const INGEST_URL_FIXTURE: IngestUrlResponse = {
  url: "https://docs.example.com/article",
  filename: "docs.example.com_article.txt",
  blob_path: "documents/docs.example.com_article.txt",
  ingestion_job_id: "22222222-2222-2222-2222-222222222222",
  queued: true,
};

const REPROCESS_FIXTURE: ReprocessResponse = {
  ingestion_job_id: "33333333-3333-3333-3333-333333333333",
  enqueued_count: 42,
};

function makeFile(
  name = "test.pdf",
  contents: BlobPart = "hello pdf",
  type = "application/pdf",
): File {
  return new File([contents], name, { type });
}

function makeOversizeFile(name = "big.pdf"): File {
  // Skip allocating 50 MiB of buffer -- Object.defineProperty lets
  // the validator see the size without paying the memory cost.
  const file = new File(["tiny"], name, { type: "application/pdf" });
  Object.defineProperty(file, "size", { value: 60 * 1024 * 1024 });
  return file;
}

beforeEach(() => {
  uploadMock.mockReset();
  addUrlMock.mockReset();
  reprocessMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("IngestData -- page shell", () => {
  it("renders the three section headings", () => {
    render(<IngestData />);
    expect(screen.getByRole("heading", { name: /ingest data/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /upload files/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /add url/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /reprocess all documents/i })).toBeInTheDocument();
  });
});

describe("IngestData -- file upload", () => {
  it("uploads a browsed file and reports success", async () => {
    uploadMock.mockResolvedValueOnce(UPLOAD_FIXTURE);
    render(<IngestData />);

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    const file = makeFile();
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      const list = screen.getByTestId("upload-list");
      expect(list.querySelectorAll("li")).toHaveLength(1);
    });
    expect(uploadMock).toHaveBeenCalledTimes(1);
    expect(uploadMock).toHaveBeenCalledWith(file);
    await waitFor(() => {
      const statuses = screen.getAllByText("success");
      expect(statuses.length).toBeGreaterThan(0);
    });
  });

  it("rejects a file over 50 MiB client-side without firing the wire call", async () => {
    render(<IngestData />);

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeOversizeFile()] } });

    await waitFor(() => {
      expect(screen.getByTestId("upload-list")).toBeInTheDocument();
    });
    expect(uploadMock).not.toHaveBeenCalled();
    const errors = screen.getAllByText(/50 MiB limit/i);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("rejects an unsupported extension client-side", async () => {
    render(<IngestData />);

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    const file = makeFile("malware.exe", "x", "application/octet-stream");
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId("upload-list")).toBeInTheDocument();
    });
    expect(uploadMock).not.toHaveBeenCalled();
    expect(screen.getByText(/Unsupported file extension/i)).toBeInTheDocument();
  });

  it("surfaces a backend error on the failed entry", async () => {
    uploadMock.mockRejectedValueOnce(
      new Error("uploadDocument: request failed with status 503"),
    );
    render(<IngestData />);

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => {
      expect(screen.getByText(/status 503/i)).toBeInTheDocument();
    });
    expect(uploadMock).toHaveBeenCalledTimes(1);
  });

  it("queues a dropped file via the dropzone", async () => {
    uploadMock.mockResolvedValueOnce(UPLOAD_FIXTURE);
    render(<IngestData />);

    const dropzone = screen.getByTestId("upload-dropzone");
    const file = makeFile("dropped.pdf");
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    await waitFor(() => {
      expect(uploadMock).toHaveBeenCalledTimes(1);
    });
    expect(uploadMock).toHaveBeenCalledWith(file);
  });

  it("retries a wire-failed upload via the retry button", async () => {
    uploadMock
      .mockRejectedValueOnce(new Error("uploadDocument: request failed with status 503"))
      .mockResolvedValueOnce(UPLOAD_FIXTURE);
    render(<IngestData />);

    const input = screen.getByTestId("upload-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    const retry = await screen.findByRole("button", { name: /retry/i });
    fireEvent.click(retry);

    await waitFor(() => {
      const successes = screen.getAllByText("success");
      expect(successes.length).toBeGreaterThan(0);
    });
    expect(uploadMock).toHaveBeenCalledTimes(2);
  });
});

describe("IngestData -- add URL", () => {
  it("submits a valid URL and reports success", async () => {
    addUrlMock.mockResolvedValueOnce(INGEST_URL_FIXTURE);
    render(<IngestData />);

    const input = screen.getByTestId("url-input") as HTMLInputElement;
    fireEvent.change(input, {
      target: { value: "https://docs.example.com/article" },
    });
    fireEvent.click(screen.getByTestId("url-submit"));

    await waitFor(() => {
      expect(addUrlMock).toHaveBeenCalledTimes(1);
    });
    expect(addUrlMock).toHaveBeenCalledWith("https://docs.example.com/article");
    await waitFor(() => {
      expect(screen.getByText(/queued for indexing/i)).toBeInTheDocument();
    });
  });

  it("rejects an invalid URL shape client-side", () => {
    render(<IngestData />);

    const input = screen.getByTestId("url-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "not a url" } });
    fireEvent.click(screen.getByTestId("url-submit"));

    expect(screen.getByTestId("url-validation-error")).toHaveTextContent(
      /not well-formed/i,
    );
    expect(addUrlMock).not.toHaveBeenCalled();
  });

  it("rejects a non-http URL scheme client-side", () => {
    render(<IngestData />);

    const input = screen.getByTestId("url-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "ftp://example.com/file" } });
    fireEvent.click(screen.getByTestId("url-submit"));

    expect(screen.getByTestId("url-validation-error")).toHaveTextContent(
      /http:\/\/ or https:\/\//i,
    );
    expect(addUrlMock).not.toHaveBeenCalled();
  });

  it("marks the URL entry failed when the backend rejects it", async () => {
    addUrlMock.mockRejectedValueOnce(
      new Error("addDocumentUrl: request failed with status 422"),
    );
    render(<IngestData />);

    const input = screen.getByTestId("url-input") as HTMLInputElement;
    fireEvent.change(input, {
      target: { value: "https://docs.example.com/article" },
    });
    fireEvent.click(screen.getByTestId("url-submit"));

    await waitFor(() => {
      expect(screen.getByText(/status 422/i)).toBeInTheDocument();
    });
    expect(addUrlMock).toHaveBeenCalledTimes(1);
  });
});

describe("IngestData -- reprocess all", () => {
  it("opens the confirmation dialog when the operator clicks reprocess", () => {
    render(<IngestData />);

    expect(screen.queryByTestId("reprocess-confirm-dialog")).toBeNull();
    fireEvent.click(screen.getByTestId("reprocess-open"));

    expect(screen.getByTestId("reprocess-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("reprocess-confirm")).toBeDisabled();
  });

  it("closes the dialog when the operator clicks cancel", () => {
    render(<IngestData />);

    fireEvent.click(screen.getByTestId("reprocess-open"));
    fireEvent.click(screen.getByTestId("reprocess-cancel"));

    expect(screen.queryByTestId("reprocess-confirm-dialog")).toBeNull();
    expect(reprocessMock).not.toHaveBeenCalled();
  });

  it("keeps the confirm button disabled until the operator types REPROCESS", () => {
    render(<IngestData />);

    fireEvent.click(screen.getByTestId("reprocess-open"));
    const confirmInput = screen.getByTestId("reprocess-confirm-input") as HTMLInputElement;
    const confirmButton = screen.getByTestId("reprocess-confirm");

    fireEvent.change(confirmInput, { target: { value: "reprocess" } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(confirmInput, { target: { value: "REPROCESS" } });
    expect(confirmButton).toBeEnabled();
  });

  it("fires reprocessAll and reports the enqueued count on success", async () => {
    reprocessMock.mockResolvedValueOnce(REPROCESS_FIXTURE);
    render(<IngestData />);

    fireEvent.click(screen.getByTestId("reprocess-open"));
    fireEvent.change(screen.getByTestId("reprocess-confirm-input"), {
      target: { value: "REPROCESS" },
    });
    fireEvent.click(screen.getByTestId("reprocess-confirm"));

    await waitFor(() => {
      expect(reprocessMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId("reprocess-success")).toHaveTextContent(
        /Enqueued 42/,
      );
    });
    expect(screen.queryByTestId("reprocess-confirm-dialog")).toBeNull();
  });

  it("surfaces a backend error and closes the dialog when reprocess fails", async () => {
    reprocessMock.mockRejectedValueOnce(
      new Error("reprocessAll: request failed with status 503"),
    );
    render(<IngestData />);

    fireEvent.click(screen.getByTestId("reprocess-open"));
    fireEvent.change(screen.getByTestId("reprocess-confirm-input"), {
      target: { value: "REPROCESS" },
    });
    fireEvent.click(screen.getByTestId("reprocess-confirm"));

    await waitFor(() => {
      expect(screen.getByTestId("reprocess-error")).toHaveTextContent(
        /status 503/i,
      );
    });
    expect(reprocessMock).toHaveBeenCalledTimes(1);
  });
});
