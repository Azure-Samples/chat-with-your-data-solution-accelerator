
# Chat History
#### **1. Introduction**
- **What is Chat History in CWYD**:
  - CWYD (Chat With Your Data) allows users to interact with their datasets conversationally. A key feature of this system is **Chat History**, which enables users to revisit past interactions for reference, auditing, or compliance purposes.

- **Purpose of this Tutorial**:
  - This tutorial guides software engineers on how to **implement** and **manage** chat history in CWYD, including enabling/disabling it.




#### **2. Enabling/Disabling Chat History in CWYD**

- **Overview**:
  - By default, chat history is stored in **CosmosDB**, which is automatically deployed with CWYD infrastructure. This feature can be toggled based on the application's needs, such as privacy considerations or resource management.

- **Steps to Enable Chat History**:
  1. **Access the Configuration**:
     - Open the CWYD administration panel.
     - Go to the "Configuration" section.
  2. **Toggle Chat History**:
     - Locate the option labeled **“Enable Chat History”**.
     - Set checkbox to enable storing conversations.
     - by default chat history is enabled.
  3. **Save and Apply**:
     - Click "Save" to apply the changes.
     - Restart the chatbot service (if required) for the changes to take effect.

- **Steps to Disable Chat History**:
  - Follow the same steps as enabling chat history, but remove checkbox. Disabling chat history will prevent storing future conversations, but it will not automatically delete past conversations.



#### **3. Accessing and Managing Chat History**

- **Viewing Chat History**:
  - If chat history is enabled, users can view their past conversations directly in the chatbot UI.
  - To view chat history, click the **"Show Chat History"** button in the chat interface.

- **Example UI Interaction**:
  - Clicking this button will open a side panel showing a list of past conversations. Users can click on each entry to review past messages and queries.

  *(Insert screenshot examples from the uploaded images showing the "Show Chat History" option)*


#### **4. Deleting Chat History**

- **How to Delete Individual Conversations**:
  1. Open the **Chat History** panel in the CWYD interface.
  2. Locate the conversation you want to delete.
  3. Click on the trash icon next to the conversation.
  4. Confirm the deletion by selecting “Delete” in the confirmation popup.

  *(Refer to the image with the delete confirmation screen for visual reference)*

- **Deleting All Chat History**:
  - Admin users can clear all chat history via the CWYD dashboard by selecting the **"Clear All Chat History"** option.
  - It is important to notify users before mass deletion, especially in applications where data retention is critical.
