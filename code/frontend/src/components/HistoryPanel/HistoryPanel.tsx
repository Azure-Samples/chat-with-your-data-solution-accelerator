import { Separator, Spinner, SpinnerSize } from "@fluentui/react";
import { forwardRef } from "react";

type HistoryPanelProps = {
    fetchingChatHistory: boolean
};

const HistoryPanel = forwardRef((props: HistoryPanelProps, ref) => {

  const { fetchingChatHistory } = props;
  return (
    <div>
      Show history list....
      {fetchingChatHistory && (
        <Spinner
          //   style={{
          //     alignSelf: "flex-start",
          //     height: "100%",
          //     marginRight: "5px",
          //   }}
          size={SpinnerSize.medium}
        />
      )}
      <div />
      <Separator
        styles={{
          root: {
            width: "100%",
            position: "relative",
            "::before": {
              backgroundColor: "#d6d6d6",
            },
          },
        }}
      />
    </div>
  );
});

export default HistoryPanel;
