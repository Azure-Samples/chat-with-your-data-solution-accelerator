import { HashRouter, Routes, Route } from "react-router-dom";
import { MsalProvider } from "@azure/msal-react";
import { IPublicClientApplication } from "@azure/msal-browser";
import Layout from "./pages/layout/Layout";
import NoPage from "./pages/NoPage";
import Chat from "./pages/chat/Chat";

type AppProps = {
    pca: IPublicClientApplication;
};

function App({ pca }: AppProps) {
  return (
    <MsalProvider instance={pca}>
      <Pages />
    </MsalProvider>
  );
}

function Pages() {
    return (
      <HashRouter>
        <Routes>
            <Route path="/" element={<Layout />}>
                <Route index element={<Chat />} />
                <Route path="*" element={<NoPage />} />
            </Route>
        </Routes>
    </HashRouter>
    );
}

export default App;
