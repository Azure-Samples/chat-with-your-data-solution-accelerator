import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";

import App from "./App";
import IngestData from "./pages/IngestData";
import ExploreData from "./pages/ExploreData";
import DeleteData from "./pages/DeleteData";
import Configuration from "./pages/Configuration";

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <FluentProvider theme={webLightTheme}>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<App />}>
                        <Route index element={<IngestData />} />
                        <Route path="ingest" element={<IngestData />} />
                        <Route path="explore" element={<ExploreData />} />
                        <Route path="delete" element={<DeleteData />} />
                        <Route path="config" element={<Configuration />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </FluentProvider>
    </React.StrictMode>
);
