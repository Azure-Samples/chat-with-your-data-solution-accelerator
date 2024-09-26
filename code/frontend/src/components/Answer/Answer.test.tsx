import "@testing-library/jest-dom";
import {
  render,
  screen,
  fireEvent,
  act,
  waitFor,
} from "@testing-library/react";
import { Answer } from "./Answer";

jest.mock(
  "react-markdown",
  () =>
    ({ children }: { children: React.ReactNode }) => {
      return <div data-testid="mock-react-markdown">{children}</div>;
    }
);
jest.mock("remark-gfm", () => () => {});
jest.mock("remark-supersub", () => () => {});

const speechMockData = {
  key: "some-key",
  languages: ["en-US", "fr-FR", "de-DE", "it-IT"],
  region: "uksouth",
  token: "some-token",
};

// Mock the Speech SDK
jest.mock("microsoft-cognitiveservices-speech-sdk", () => {
  return {
    SpeechConfig: {
      fromSubscription: jest.fn(),
      fromSpeakerOutput: jest.fn().mockReturnValue({}),
    },
    AudioConfig: {
      fromDefaultSpeakerOutput: jest.fn(),
      fromSpeakerOutput: jest.fn().mockReturnValue({}),
    },
    SpeechSynthesizer: jest.fn().mockImplementation(() => ({
      speakTextAsync: jest.fn((text, callback) => {
        callback({
          audioData: new ArrayBuffer(1024),
          audioDuration: 999999999999,
          reason: 10,
        });
      }),
      close: jest.fn(),
    })),

    SpeakerAudioDestination: jest.fn().mockImplementation(() => ({
      pause: jest.fn(),
      resume: jest.fn(),
      close: jest.fn(),
    })),
    ResultReason: {
      SynthesizingAudioCompleted: 10,
      Canceled: 1,
    },
  };
});

const componentPropsWithCitations = {
  answer: {
    answer:
      "Microsoft AI encompasses a wide range of technologies and solutions that leverage artificial intelligence to empower individuals and organizations. Microsoft's AI platform, Azure AI, helps organizations transform by bringing intelligence and insights to solve their most pressing challenges[doc2]. Azure AI offers enterprise-level and responsible AI protections, enabling organizations to achieve more at scale[doc8]. Microsoft has a long-term partnership with OpenAI and deploys OpenAI's models across its consumer and enterprise products[doc5]. The company is committed to making the promise of AI real and doing it responsibly, guided by principles such as fairness, reliability and safety, privacy and security, inclusiveness, transparency, and accountability[doc1]. Microsoft's AI offerings span various domains, including productivity services, cloud computing, mixed reality, conversational AI, data analytics, and more[doc3][doc6][doc4]. These AI solutions aim to enhance productivity, improve customer experiences, optimize business functions, and drive innovation[doc9][doc7]. However, the adoption of AI also presents challenges and risks, such as biased datasets, ethical considerations, and potential legal and reputational harm[doc11]. Microsoft is committed to addressing these challenges and ensuring the responsible development and deployment of AI technologies[doc10].",
    citations: [
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>\n<p>We have a long-term partnership with OpenAI, a leading AI research and deployment company. We deploy OpenAI’s models across our consumer and enterprise products. As OpenAI’s exclusive cloud provider, Azure powers all of OpenAI's workloads. We have also increased our investments in the development and deployment of specialized supercomputing systems to accelerate OpenAI’s research.</p>\n<p>Our hybrid infrastructure offers integrated, end-to-end security, compliance, identity, and management capabilities to support the real-world needs and evolving regulatory requirements of commercial customers and enterprises. Our industry clouds bring together capabilities across the entire Microsoft Cloud, along with industry-specific customizations. Azure Arc simplifies governance and management by delivering a consistent multi-cloud and on-premises management platform.</p>\n<p>Nuance, a leader in conversational AI and ambient intelligence across industries including healthcare, financial services, retail, and telecommunications, joined Microsoft in 2022. Microsoft and Nuance enable organizations to accelerate their business goals with security-focused, cloud-based solutions infused with AI.</p>\n<p>We are accelerating our development of mixed reality solutions with new Azure services and devices. Microsoft Mesh enables organizations to create custom, immersive experiences for the workplace to help bring remote and hybrid workers and teams together. </p>\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>",
        id: "doc_7ff8f57d63e2eebb0a3372db05153822fdee65e6",
        chunk_id: 7,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>\n<p>We have a long-term partnership with OpenAI, a leading AI research and deployment company. We deploy OpenAI’s models across our consumer and enterprise products. As OpenAI’s exclusive cloud provider, Azure powers all of OpenAI's workloads. We have also increased our investments in the development and deployment of specialized supercomputing systems to accelerate OpenAI’s research.</p>\n<p>Our hybrid infrastructure offers integrated, end-to-end security, compliance, identity, and management capabilities to support the real-world needs and evolving regulatory requirements of commercial customers and enterprises. Our industry clouds bring together capabilities across the entire Microsoft Cloud, along with industry-specific customizations. Azure Arc simplifies governance and management by delivering a consistent multi-cloud and on-premises management platform.</p>\n<p>Nuance, a leader in conversational AI and ambient intelligence across industries including healthcare, financial services, retail, and telecommunications, joined Microsoft in 2022. Microsoft and Nuance enable organizations to accelerate their business goals with security-focused, cloud-based solutions infused with AI.</p>\n<p>We are accelerating our development of mixed reality solutions with new Azure services and devices. Microsoft Mesh enables organizations to create custom, immersive experiences for the workplace to help bring remote and hybrid workers and teams together. </p>\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>",
        id: "doc_7ff8f57d63e2eebb0a3372db05153822fdee65e6",
        chunk_id: 7,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>\n<p>We have a long-term partnership with OpenAI, a leading AI research and deployment company. We deploy OpenAI’s models across our consumer and enterprise products. As OpenAI’s exclusive cloud provider, Azure powers all of OpenAI's workloads. We have also increased our investments in the development and deployment of specialized supercomputing systems to accelerate OpenAI’s research.</p>\n<p>Our hybrid infrastructure offers integrated, end-to-end security, compliance, identity, and management capabilities to support the real-world needs and evolving regulatory requirements of commercial customers and enterprises. Our industry clouds bring together capabilities across the entire Microsoft Cloud, along with industry-specific customizations. Azure Arc simplifies governance and management by delivering a consistent multi-cloud and on-premises management platform.</p>\n<p>Nuance, a leader in conversational AI and ambient intelligence across industries including healthcare, financial services, retail, and telecommunications, joined Microsoft in 2022. Microsoft and Nuance enable organizations to accelerate their business goals with security-focused, cloud-based solutions infused with AI.</p>\n<p>We are accelerating our development of mixed reality solutions with new Azure services and devices. Microsoft Mesh enables organizations to create custom, immersive experiences for the workplace to help bring remote and hybrid workers and teams together. </p>\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>",
        id: "doc_7ff8f57d63e2eebb0a3372db05153822fdee65e6",
        chunk_id: 7,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>PART I</p>\n<p>ITEM 1. BUSINESS</p>\n<p>GENERAL</p>\n<p>Embracing Our Future</p>\n<p>Microsoft is a technology company whose mission is to empower every person and every organization on the planet to achieve more. We strive to create local opportunity, growth, and impact in every country around the world. We are creating the platforms and tools, powered by artificial intelligence (“AI”), that deliver better, faster, and more effective solutions to support small and large business competitiveness, improve educational and health outcomes, grow public-sector efficiency, and empower human ingenuity. From infrastructure and data, to business applications and collaboration, we provide unique, differentiated value to customers. </p>\n<p>In a world of increasing economic complexity, AI has the power to revolutionize many types of work. Microsoft is now innovating and expanding our portfolio with AI capabilities to help people and organizations overcome today’s challenges and emerge stronger. Customers are looking to unlock value from their digital spend and innovate for this next generation of AI, while simplifying security and management. Those leveraging the Microsoft Cloud are best positioned to take advantage of technological advancements and drive innovation. Our investment in AI spans the entire company, from Microsoft Teams and Outlook, to Bing and Xbox, and we are infusing generative AI capability into our consumer and commercial offerings to deliver copilot capability for all services across the Microsoft Cloud. </p>\n<p>We’re committed to making the promise of AI real – and doing it responsibly. Our work is guided by a core set of principles: fairness, reliability and safety, privacy and security, inclusiveness, transparency, and accountability. </p>\n<p>What We Offer</p>\n<p>Founded in 1975, we develop and support software, services, devices, and solutions that deliver new value for customers and help people and businesses realize their full potential.</p>\n<p>We offer an array of services, including cloud-based solutions that provide customers with software, services, platforms, and content, and we provide solution support and consulting services. We also deliver relevant online advertising to a global audience.</p>",
        id: "doc_14b4ad620c24c5a472f0c4505019c5370b814e17",
        chunk_id: 4,
        title:
          "/documents/MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx",
        filepath:
          "MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx",
        url: "[/documents/MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K_DOCUMENT_FOLDER_SRC_IMPORTANT_CHUNKS_LIST_VALID_CHUNKS_ACCESS_TO_MSFT_WINDOWS_BLOBS_CORE_WINDOWS.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>\n<p>We have a long-term partnership with OpenAI, a leading AI research and deployment company. We deploy OpenAI’s models across our consumer and enterprise products. As OpenAI’s exclusive cloud provider, Azure powers all of OpenAI's workloads. We have also increased our investments in the development and deployment of specialized supercomputing systems to accelerate OpenAI’s research.</p>\n<p>Our hybrid infrastructure offers integrated, end-to-end security, compliance, identity, and management capabilities to support the real-world needs and evolving regulatory requirements of commercial customers and enterprises. Our industry clouds bring together capabilities across the entire Microsoft Cloud, along with industry-specific customizations. Azure Arc simplifies governance and management by delivering a consistent multi-cloud and on-premises management platform.</p>\n<p>Nuance, a leader in conversational AI and ambient intelligence across industries including healthcare, financial services, retail, and telecommunications, joined Microsoft in 2022. Microsoft and Nuance enable organizations to accelerate their business goals with security-focused, cloud-based solutions infused with AI.</p>\n<p>We are accelerating our development of mixed reality solutions with new Azure services and devices. Microsoft Mesh enables organizations to create custom, immersive experiences for the workplace to help bring remote and hybrid workers and teams together. </p>\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>",
        id: "doc_7ff8f57d63e2eebb0a3372db05153822fdee65e6",
        chunk_id: 7,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>\n<p>GitHub Copilot is at the forefront of AI-powered software development, giving developers a new tool to write code easier and faster so they can focus on more creative problem-solving. From GitHub to Visual Studio, we provide a developer tool chain for everyone, no matter the technical experience, across all platforms, whether Azure, Windows, or any other cloud or client platform.</p>\n<p>Windows also plays a critical role in fueling our cloud business with Windows 365, a desktop operating system that’s also a cloud service. From another internet-connected device, including Android or macOS devices, users can run Windows 365, just like a virtual machine.</p>\n<p>Additionally, we are extending our infrastructure beyond the planet, bringing cloud computing to space. Azure Orbital is a fully managed ground station as a service for fast downlinking of data.</p>\n<p>Create More Personal Computing</p>\n<p>We strive to make computing more personal, enabling users to interact with technology in more intuitive, engaging, and dynamic ways. </p>\n<p>Windows 11 offers innovations focused on enhancing productivity, including Windows Copilot with centralized AI assistance and Dev Home to help developers become more productive. Windows 11 security and privacy features include operating system security, application security, and user and identity security. </p>\n<p>Through our Search, News, Mapping, and Browser services, Microsoft delivers unique trust, privacy, and safety features. In February 2023, we launched an all new, AI-powered Microsoft Edge browser and Bing search engine with Bing Chat to deliver better search, more complete answers, and the ability to generate content. Microsoft Edge is our fast and secure browser that helps protect users’ data. Quick access to AI-powered tools, apps, and more within Microsoft Edge’s sidebar enhance browsing capabilities.</p>",
        id: "doc_d85da45581d92f2ff59e261197d2c70c2b6f8802",
        chunk_id: 8,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Together with the Microsoft Cloud, Dynamics 365, Microsoft Teams, and our AI offerings bring a new era of collaborative applications that optimize business functions, processes, and applications to better serve customers and employees while creating more business value. Microsoft Power Platform is helping domain experts drive productivity gains with low-code/no-code tools, robotic process automation, virtual agents, and business intelligence. In a dynamic labor market, LinkedIn is helping professionals use the platform to connect, learn, grow, and get hired. </p>\n<p>Build the Intelligent Cloud and Intelligent Edge Platform</p>\n<p>As digital transformation and adoption of AI accelerates and revolutionizes more business workstreams, organizations in every sector across the globe can address challenges that will have a fundamental impact on their success. For enterprises, digital technology empowers employees, optimizes operations, engages customers, and in some cases, changes the very core of products and services. We continue to invest in high performance and sustainable computing to meet the growing demand for fast access to Microsoft services provided by our network of cloud computing infrastructure and datacenters. </p>\n<p>Our cloud business benefits from three economies of scale: datacenters that deploy computational resources at significantly lower cost per unit than smaller ones; datacenters that coordinate and aggregate diverse customer, geographic, and application demand patterns, improving the utilization of computing, storage, and network resources; and multi-tenancy locations that lower application maintenance labor costs.</p>\n<p>The Microsoft Cloud provides the best integration across the technology stack while offering openness, improving time to value, reducing costs, and increasing agility. Being a global-scale cloud, Azure uniquely offers hybrid consistency, developer productivity, AI capabilities, and trusted security and compliance. We see more emerging use cases and needs for compute and security at the edge and are accelerating our innovation across the spectrum of intelligent edge devices, from Internet of Things (“IoT”) sensors to gateway devices and edge hardware to build, manage, and secure edge workloads. </p>\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>",
        id: "doc_3a2261beeaf7820dfdcc3b0d51a58bd981555b92",
        chunk_id: 6,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>\n<p>We have a long-term partnership with OpenAI, a leading AI research and deployment company. We deploy OpenAI’s models across our consumer and enterprise products. As OpenAI’s exclusive cloud provider, Azure powers all of OpenAI's workloads. We have also increased our investments in the development and deployment of specialized supercomputing systems to accelerate OpenAI’s research.</p>\n<p>Our hybrid infrastructure offers integrated, end-to-end security, compliance, identity, and management capabilities to support the real-world needs and evolving regulatory requirements of commercial customers and enterprises. Our industry clouds bring together capabilities across the entire Microsoft Cloud, along with industry-specific customizations. Azure Arc simplifies governance and management by delivering a consistent multi-cloud and on-premises management platform.</p>\n<p>Nuance, a leader in conversational AI and ambient intelligence across industries including healthcare, financial services, retail, and telecommunications, joined Microsoft in 2022. Microsoft and Nuance enable organizations to accelerate their business goals with security-focused, cloud-based solutions infused with AI.</p>\n<p>We are accelerating our development of mixed reality solutions with new Azure services and devices. Microsoft Mesh enables organizations to create custom, immersive experiences for the workplace to help bring remote and hybrid workers and teams together. </p>\n<p>The ability to convert data into AI drives our competitive advantage. The Microsoft Intelligent Data Platform is a leading cloud data platform that fully integrates databases, analytics, and governance. The platform empowers organizations to invest more time creating value rather than integrating and managing their data. Microsoft Fabric is an end-to-end, unified analytics platform that brings together all the data and analytics tools that organizations need. </p>",
        id: "doc_7ff8f57d63e2eebb0a3372db05153822fdee65e6",
        chunk_id: 7,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Together with the Microsoft Cloud, Dynamics 365, Microsoft Teams, and our AI offerings bring a new era of collaborative applications that optimize business functions, processes, and applications to better serve customers and employees while creating more business value. Microsoft Power Platform is helping domain experts drive productivity gains with low-code/no-code tools, robotic process automation, virtual agents, and business intelligence. In a dynamic labor market, LinkedIn is helping professionals use the platform to connect, learn, grow, and get hired. </p>\n<p>Build the Intelligent Cloud and Intelligent Edge Platform</p>\n<p>As digital transformation and adoption of AI accelerates and revolutionizes more business workstreams, organizations in every sector across the globe can address challenges that will have a fundamental impact on their success. For enterprises, digital technology empowers employees, optimizes operations, engages customers, and in some cases, changes the very core of products and services. We continue to invest in high performance and sustainable computing to meet the growing demand for fast access to Microsoft services provided by our network of cloud computing infrastructure and datacenters. </p>\n<p>Our cloud business benefits from three economies of scale: datacenters that deploy computational resources at significantly lower cost per unit than smaller ones; datacenters that coordinate and aggregate diverse customer, geographic, and application demand patterns, improving the utilization of computing, storage, and network resources; and multi-tenancy locations that lower application maintenance labor costs.</p>\n<p>The Microsoft Cloud provides the best integration across the technology stack while offering openness, improving time to value, reducing costs, and increasing agility. Being a global-scale cloud, Azure uniquely offers hybrid consistency, developer productivity, AI capabilities, and trusted security and compliance. We see more emerging use cases and needs for compute and security at the edge and are accelerating our innovation across the spectrum of intelligent edge devices, from Internet of Things (“IoT”) sensors to gateway devices and edge hardware to build, manage, and secure edge workloads. </p>\n<p>Our AI platform, Azure AI, is helping organizations transform, bringing intelligence and insights to the hands of their employees and customers to solve their most pressing challenges. Organizations large and small are deploying Azure AI solutions to achieve more at scale, more easily, with the proper enterprise-level and responsible AI protections.</p>",
        id: "doc_3a2261beeaf7820dfdcc3b0d51a58bd981555b92",
        chunk_id: 6,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Issues in the development and use of AI may result in reputational or competitive harm or liability. We are building AI into many of our offerings, including our productivity services, and we are also making AI available for our customers to use in solutions that they build. This AI may be developed by Microsoft or others, including our strategic partner, OpenAI. We expect these elements of our business to grow. We envision a future in which AI operating in our devices, applications, and the cloud helps our customers be more productive in their work and personal lives. As with many innovations, AI presents risks and challenges that could affect its adoption, and therefore our business. AI algorithms or training methodologies may be flawed. Datasets may be overbroad, insufficient, or contain biased information. Content generated by AI systems may be offensive, illegal, or otherwise harmful. Ineffective or inadequate AI development or deployment practices by Microsoft or others could result in incidents that impair the acceptance of AI solutions or cause harm to individuals, customers, or society, or result in our products and services not working as intended. Human review of certain outputs may be required. As a result of these and other challenges associated with innovative technologies, our implementation of AI systems could subject us to competitive harm, regulatory action, legal liability, including under new proposed legislation regulating AI in jurisdictions such as the European Union (“EU”), new applications of existing data protection, privacy, intellectual property, and other laws, and brand or reputational harm. Some AI scenarios present ethical issues or may have broad impacts on society. If we enable or offer AI solutions that have unintended consequences, unintended usage or customization by our customers and partners, or are controversial because of their impact on human rights, privacy, employment, or other social, economic, or political issues, we may experience brand or reputational harm, adversely affecting our business and consolidated financial statements.</p>\n<p>OPERATIONAL RISKS</p>",
        id: "doc_0b803fe4ec1406115ee7f35a9dd9060ad5d905f5",
        chunk_id: 57,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
      {
        content:
          "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)\n\n\n<p>Issues in the development and use of AI may result in reputational or competitive harm or liability. We are building AI into many of our offerings, including our productivity services, and we are also making AI available for our customers to use in solutions that they build. This AI may be developed by Microsoft or others, including our strategic partner, OpenAI. We expect these elements of our business to grow. We envision a future in which AI operating in our devices, applications, and the cloud helps our customers be more productive in their work and personal lives. As with many innovations, AI presents risks and challenges that could affect its adoption, and therefore our business. AI algorithms or training methodologies may be flawed. Datasets may be overbroad, insufficient, or contain biased information. Content generated by AI systems may be offensive, illegal, or otherwise harmful. Ineffective or inadequate AI development or deployment practices by Microsoft or others could result in incidents that impair the acceptance of AI solutions or cause harm to individuals, customers, or society, or result in our products and services not working as intended. Human review of certain outputs may be required. As a result of these and other challenges associated with innovative technologies, our implementation of AI systems could subject us to competitive harm, regulatory action, legal liability, including under new proposed legislation regulating AI in jurisdictions such as the European Union (“EU”), new applications of existing data protection, privacy, intellectual property, and other laws, and brand or reputational harm. Some AI scenarios present ethical issues or may have broad impacts on society. If we enable or offer AI solutions that have unintended consequences, unintended usage or customization by our customers and partners, or are controversial because of their impact on human rights, privacy, employment, or other social, economic, or political issues, we may experience brand or reputational harm, adversely affecting our business and consolidated financial statements.</p>\n<p>OPERATIONAL RISKS</p>",
        id: "doc_0b803fe4ec1406115ee7f35a9dd9060ad5d905f5",
        chunk_id: 57,
        title: "/documents/MSFT_FY23Q4_10K.docx",
        filepath: "MSFT_FY23Q4_10K.docx",
        url: "[/documents/MSFT_FY23Q4_10K.docx](https://str5z43dncphzu3k.blob.core.windows.net/documents/MSFT_FY23Q4_10K.docx?se=2024-09-25T10%3A24%3A29Z&sp=r&sv=2024-05-04&sr=c&sig=A0VRcSG23IfL3O1lCh34x7IxIvE0/Fq6vT3zCqWSLig%3D)",
        metadata: null,
      },
    ],
  },
  isActive: false,
  index: 2,
};

const createFetchResponse = (ok: boolean, data: any) => {
  return { ok: ok, json: () => new Promise((resolve) => resolve(data)) };
};

describe("Answer.tsx", () => {
  const mockCitationClick = jest.fn();
  const mockOnSpeak = jest.fn();
  beforeEach(() => {
    global.fetch = jest.fn();
    Element.prototype.scrollIntoView = jest.fn();
  });
  afterEach(() => {
    jest.clearAllMocks();
  });

  test("AI Generated Content Incorrect Text should be found", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{ answer: "User Question 1", citations: [] }}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
          isActive={true}
          index={0}
        />
      );
    });
    const AIGeneratedContentElement = screen.getByText(
      /ai\-generated content may be incorrect/i
    );
    expect(AIGeneratedContentElement).toBeInTheDocument();
  });

  // test("on speech response failure handled properly", async () => {
  //   (global.fetch as jest.Mock).mockResolvedValue(
  //     createFetchResponse(false, "Error response message")
  //   );

  //   await act(async () => {
  //     render(
  //       <Answer
  //         answer={{ answer: "User Question 1", citations: [] }}
  //         onCitationClicked={mockCitationClick}
  //         onSpeak={mockOnSpeak}
  //         isActive={true}
  //         index={0}
  //       />
  //     );
  //   });
  //   const AIGeneratedContentElement = screen.getByText(
  //     /ai\-generated content may be incorrect/i
  //   );
  //   expect(AIGeneratedContentElement).toBeInTheDocument();
  // });

  test("No Of Citations Should Show 5 references", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const referencesElement = screen.getByTestId("no-of-references");
    expect(referencesElement).toBeInTheDocument();
    expect(referencesElement.textContent).toEqual("5 references");
  });

  test("On Click references show citations list", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const referencesElement = screen.getByTestId("toggle-citations-list");
    await act(async () => {
      fireEvent.click(referencesElement);
    });
    const citationsListContainer = screen.getByTestId("citations-container");
    expect(citationsListContainer.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  test("Should be able click Chevron to get citation list", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const chevronIcon = screen.getByTestId("chevron-icon");
    await act(async () => {
      fireEvent.click(chevronIcon);
    });
    const citationsListContainer = screen.getByTestId("citations-container");
    expect(citationsListContainer.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
    });
  });

  test("should be able to click play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    const playBtnAfterClick = screen.queryByTestId("play-button");
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(playBtnAfterClick).not.toBeInTheDocument();
    expect(pauseBtnAfterClick).toBeInTheDocument();
  });

  test("should be able to play pause and play again", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(pauseBtnAfterClick).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(pauseBtnAfterClick);
    });
    const playBtnAfterPause = screen.queryByTestId("play-button");
    expect(playBtnAfterPause).toBeInTheDocument();
  });

  test("should be able to pause after play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    const pauseBtn = screen.queryByTestId("pause-button");
    expect(playBtn).toBeInTheDocument();
    expect(pauseBtn).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
    const pauseBtnAfterClick = screen.getByTestId("pause-button");
    expect(pauseBtnAfterClick).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(pauseBtnAfterClick);
    });
    await waitFor(
      async () => {
        const playBtnAfterPause = screen.queryByTestId("play-button");
        expect(playBtnAfterPause).toBeInTheDocument();
        await act(async () => {
          fireEvent.click(pauseBtnAfterClick);
        });
      },
      { timeout: 3000 }
    );
  });

  test("should be able to get synthesized audio after clicking play", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    // let reRender;
    await act(async () => {
      render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });
    await waitFor(() => {}, { timeout: 4000 });
  });

  test("on change of isActive prop playing audio should stop", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    let reRender: (ui: React.ReactNode) => void;
    await act(async () => {
      const { rerender } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
      reRender = rerender;
    });

    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });

    await act(async () => {
      const pauseBtn = screen.getByTestId("pause-button");
      expect(pauseBtn).toBeInTheDocument();
      reRender(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={false}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playAfterActiveFalse = screen.getByTestId("play-button");
    expect(playAfterActiveFalse).toBeInTheDocument();
  });

  test("on index prop update new synthesizer to be initialized", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      createFetchResponse(true, speechMockData)
    );
    let reRender: (ui: React.ReactNode) => void;
    await act(async () => {
      const { rerender } = render(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={true}
          index={2}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
      reRender = rerender;
    });

    const playBtn = screen.getByTestId("play-button");
    expect(playBtn).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(playBtn);
    });

    await act(async () => {
      const pauseBtn = screen.getByTestId("pause-button");
      expect(pauseBtn).toBeInTheDocument();
      reRender(
        <Answer
          answer={{
            answer: componentPropsWithCitations.answer.answer,
            citations: componentPropsWithCitations.answer.citations,
          }}
          isActive={false}
          index={3}
          onCitationClicked={mockCitationClick}
          onSpeak={mockOnSpeak}
        />
      );
    });
    const playAfterActiveFalse = screen.getByTestId("play-button");
    expect(playAfterActiveFalse).toBeInTheDocument();
  });
});
