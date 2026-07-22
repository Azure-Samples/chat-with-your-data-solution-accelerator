---
title: Speech-to-text
description: How Chat with Your Data adds voice input using Azure AI Speech and a short-lived, secretless authorization token.
ms.date: 2026-07-03
ms.topic: overview
---

[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)

## Overview

Many people are used to speech-to-text in their consumer apps. With hybrid work, voice input gives users a flexible way to chat with their data, at their computer or on the go with a mobile device. Chat with Your Data pairs speech recognition with the assistant so users can speak a question and get a grounded answer back.

*(Replace this with a screenshot of the chat page and its microphone control in your deployment.)*

## How it works

Speech recognition runs in the browser with the Azure AI Speech SDK. The backend never streams audio. Instead, when the web app starts recognition, it calls the backend, which mints a short-lived (10-minute) authorization token from the Speech service and returns it along with the region and the configured languages. The browser uses that token to transcribe speech to text, which is then sent as a chat question.

Because the backend authenticates to the Speech service with the workload's managed identity, the token is issued through Microsoft Entra; there is no Speech subscription key anywhere in the app. See [Managed identity and RBAC](managed_identity.md).

## What is deployed

* An Azure AI Speech resource, provisioned alongside the other services.
* A role assignment that lets the workload's managed identity mint tokens from the Speech resource.

All three application services, including the backend that mints the token, run on Azure Container Apps. See [Architecture overview](architecture.md).

## Recognition languages

Recognition supports multiple languages. By default the app recognizes `en-US`, `fr-FR`, `de-DE`, and `it-IT`. The set is provided to the browser by the backend from the `AZURE_SPEECH_RECOGNIZER_LANGUAGES` setting, a comma-separated list you can adjust on the backend service.

## Related documentation

* [Architecture overview](architecture.md)
* [Managed identity and RBAC](managed_identity.md)
* [Streaming answers and citations](streaming_responses.md)
