import React from "react";
import { render, screen } from "@testing-library/react";
import { AssistantTypeSection } from "./AssistantTypeSection";
//import { assistantTypes } from "./AssistantTypeSection";
import Cards from "../../pages/chat/Cards_contract/Cards";

// Mock the Cards component
jest.mock("../../pages/chat/Cards_contract/Cards", () => () => <div>Mocked Cards Component</div>);

jest.mock("../../assets/Azure.svg", () => "mock-azure-svg");

enum assistantTypes {
    default = "default",
    contractAssistant = "contract assistant",
  }

describe("AssistantTypeSection", () => {
  test("renders Contract Summarizer section when assistantType is contractAssistant", () => {
    render(
      <AssistantTypeSection
        assistantType={assistantTypes.contractAssistant}
        isAssistantAPILoading={false}
      />
    );

    expect(screen.getByText("Contract Summarizer")).toBeInTheDocument();
    expect(
      screen.getByText("AI-Powered assistant for simplified summarization")
    ).toBeInTheDocument();
    expect(screen.getByText("Mocked Cards Component")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  test("renders default assistant section when assistantType is default", () => {
    render(
      <AssistantTypeSection
        assistantType={assistantTypes.default}
        isAssistantAPILoading={false}
      />
    );

    expect(screen.getByText("Chat with your")).toBeInTheDocument();
    //expect(screen.getByText("\u00a0Data")).toBeInTheDocument();
    expect(
      screen.getByText("This chatbot is configured to answer your questions")
    ).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  test("does not render anything if assistantType is not recognized", () => {
    render(
      <AssistantTypeSection
        assistantType="unknown"
        isAssistantAPILoading={false}
      />
    );

    expect(screen.queryByText("Chat with your")).not.toBeInTheDocument();
    expect(screen.queryByText("Contract Summarizer")).not.toBeInTheDocument();
    expect(screen.queryByText("Mocked Cards Component")).not.toBeInTheDocument();
  });

  test("renders the loading spinner when isAssistantAPILoading is true", () => {
    render(
      <AssistantTypeSection
        assistantType={assistantTypes.default}
        isAssistantAPILoading={true}
      />
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByRole("img", { hidden: true })).toBeInTheDocument();
  });

  test("renders both the assistant content and loading spinner when isAssistantAPILoading is true", () => {
    render(
      <AssistantTypeSection
        assistantType={assistantTypes.contractAssistant}
        isAssistantAPILoading={true}
      />
    );

    expect(screen.getByText("Contract Summarizer")).toBeInTheDocument();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByRole("img", { hidden: true })).toBeInTheDocument();
  });
});
