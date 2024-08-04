import streamlit as st
import os
import traceback
import logging
from dotenv import load_dotenv
import sys
from batch.utilities.helpers.ConfigHelper import ConfigHelper
from components.login import isLoggedIn
from components.menu import menu

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)


def main():
    st.set_page_config(
        page_title="Configure Prompts",
        page_icon=os.path.join("images", "favicon.ico"),
        layout="wide",
        menu_items=None,
    )
    menu()

    mod_page_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(mod_page_style, unsafe_allow_html=True)

    config = ConfigHelper.get_active_config_or_default()

    # Populate all fields from Config values
    # # # if 'condense_question_prompt' not in st.session_state:
    # # #     st.session_state['condense_question_prompt'] = config.prompts.condense_question_prompt
    if "answering_prompt" not in st.session_state:
        st.session_state["answering_prompt"] = config.prompts.answering_prompt
    if "post_answering_prompt" not in st.session_state:
        st.session_state["post_answering_prompt"] = config.prompts.post_answering_prompt
    if "enable_post_answering_prompt" not in st.session_state:
        st.session_state["enable_post_answering_prompt"] = (
            config.prompts.enable_post_answering_prompt
        )
    if "post_answering_filter_message" not in st.session_state:
        st.session_state["post_answering_filter_message"] = (
            config.messages.post_answering_filter
        )
    if "enable_content_safety" not in st.session_state:
        st.session_state["enable_content_safety"] = config.prompts.enable_content_safety

    if "log_user_interactions" not in st.session_state:
        st.session_state["log_user_interactions"] = config.logging.log_user_interactions
    if "log_tokens" not in st.session_state:
        st.session_state["log_tokens"] = config.logging.log_tokens

    if "orchestrator_strategy" not in st.session_state:
        st.session_state["orchestrator_strategy"] = config.orchestrator.strategy.value

    # # # def validate_question_prompt():
    # # #     if "{chat_history}" not in st.session_state.condense_question_prompt:
    # # #         st.warning("Your condense question prompt doesn't contain the variable `{chat_history}`")
    # # #     if "{question}" not in st.session_state.condense_question_prompt:
    # # #         st.warning("Your condense question prompt doesn't contain the variable `{question}`")

    def validate_answering_prompt():
        if "{sources}" not in st.session_state.answering_prompt:
            st.warning("Your answering prompt doesn't contain the variable `{sources}`")
        if "{question}" not in st.session_state.answering_prompt:
            st.warning(
                "Your answering prompt doesn't contain the variable `{question}`"
            )

    def validate_post_answering_prompt():
        if (
            "post_answering_prompt" not in st.session_state
            or len(st.session_state.post_answering_prompt) == 0
        ):
            pass
        if "{sources}" not in st.session_state.post_answering_prompt:
            st.warning(
                "Your post answering prompt doesn't contain the variable `{sources}`"
            )
        if "{question}" not in st.session_state.post_answering_prompt:
            st.warning(
                "Your post answering prompt doesn't contain the variable `{question}`"
            )
        if "{answer}" not in st.session_state.post_answering_prompt:
            st.warning(
                "Your post answering prompt doesn't contain the variable `{answer}`"
            )


    try:
        with st.expander("Orchestrator configuration", expanded=True):
            cols = st.columns([2, 4])
            with cols[0]:
                st.selectbox(
                    "Orchestrator strategy",
                    key="orchestrator_strategy",
                    options=config.get_available_orchestration_strategies(),
                )

        # # # condense_question_prompt_help = "This prompt is used to convert the user's input to a standalone question, using the context of the chat history."
        answering_prompt_help = "This prompt is used to answer the user's question, using the sources that were retrieved from the knowledge base."
        post_answering_prompt_help = "You can configure a post prompt that allows to fact-check or process the answer, given the sources, question and answer. This prompt needs to return `True` or `False`."
        post_answering_filter_help = "The message that is returned to the user, when the post-answering prompt returns."

        with st.expander("Prompt configuration", expanded=True):
            # # # st.text_area("Condense question prompt", key='condense_question_prompt', on_change=validate_question_prompt, help=condense_question_prompt_help, height=200)
            st.text_area(
                "Answering prompt",
                key="answering_prompt",
                on_change=validate_answering_prompt,
                help=answering_prompt_help,
                height=400,
            )

            st.text_area(
                "Post-answering prompt",
                key="post_answering_prompt",
                on_change=validate_post_answering_prompt,
                help=post_answering_prompt_help,
                height=200,
            )
            st.checkbox(
                "Enable post-answering prompt", key="enable_post_answering_prompt"
            )
            st.text_area(
                "Post-answering filter message",
                key="post_answering_filter_message",
                help=post_answering_filter_help,
                height=200,
            )

            st.checkbox("Enable Azure AI Content Safety", key="enable_content_safety")

        document_processors = list(
            map(
                lambda x: {
                    "document_type": x.document_type,
                    "chunking_strategy": x.chunking.chunking_strategy.value,
                    "chunking_size": x.chunking.chunk_size,
                    "chunking_overlap": x.chunking.chunk_overlap,
                    "loading_strategy": x.loading.loading_strategy.value,
                },
                config.document_processors,
            )
        )
        with st.expander("Document processing configuration", expanded=True):
            edited_document_processors = st.data_editor(
                data=document_processors,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "document_type": st.column_config.SelectboxColumn(
                        options=config.get_available_document_types()
                    ),
                    "chunking_strategy": st.column_config.SelectboxColumn(
                        options=[
                            cs for cs in config.get_available_chunking_strategies()
                        ]
                    ),
                    "loading_strategy": st.column_config.SelectboxColumn(
                        options=[ls for ls in config.get_available_loading_strategies()]
                    ),
                },
            )

        with st.expander("Logging configuration", expanded=True):
            st.checkbox(
                "Log user input and output (questions, answers, chat history, sources)",
                key="log_user_interactions",
            )
            st.checkbox("Log tokens", key="log_tokens")


        crawler_config = config.crawling
        with st.expander("Crawler configuration", expanded=True):
            crawl_enabled = st.checkbox("Enable crawling", value=crawler_config.crawl_enabled, key="crawl_enabled")
            if crawl_enabled:
                st.text_area("Crawl target URLs(split by space)", value=crawler_config.crawl_target_urls, key="crawl_target_urls", help="Enter URLs separated by space")
                
                
                st.markdown("### Cron Schedule")
                with st.container():  # Create a container for the cron schedule fields
                     # Input fields for the cron expression components
                    crawl_schedule_second = st.number_input("Second", min_value=0, max_value=59, value=crawler_config.crawl_cron.seconds, key="seconds")  # Input for second
                    crawl_schedule_minute = st.number_input("Minute", min_value=0, max_value=59, value=crawler_config.crawl_cron.minutes, key="minutes")
                    crawl_schedule_hour = st.number_input("Hour", min_value=0, max_value=23, value=crawler_config.crawl_cron.hours, key="hours")
                    crawl_schedule_day = st.number_input("Day of Month", min_value=1, max_value=31, value=crawler_config.crawl_cron.days, key="days")
                    crawl_schedule_month = st.number_input("Month", min_value=1, max_value=12, value=crawler_config.crawl_cron.months, key="months")
                    # Select box for day of week with options
                    crawl_schedule_day_of_week = st.selectbox("Day of Week", ["*", "0 (Sunday)", "1 (Monday)", "2 (Tuesday)", "3 (Wednesday)", "4 (Thursday)", "5 (Friday)", "6 (Saturday)"], key="day_of_week")

                    if crawl_schedule_day_of_week != "*":
                        crawl_schedule_day_of_week = crawl_schedule_day_of_week.split()[0]

                    crawl_schedule_str = f"{crawl_schedule_second} {crawl_schedule_minute} {crawl_schedule_hour} {crawl_schedule_day} {crawl_schedule_month} {crawl_schedule_day_of_week}"
                    st.write(f"Cron Schedule: `{crawl_schedule_str}`")  # Display the generated cron schedule



                crawl_delay_seconds_str = st.text_input("Crawl delay (seconds)", value=str(crawler_config.crawl_delay_seconds), key="crawl_delay_seconds")
                crawl_retry_count_str = st.text_input("Crawl retry count", value=str(crawler_config.crawl_retry_count), key="crawl_retry_count")

                # Convert the string inputs back to integers with validation
                try:
                    crawl_delay_seconds = int(crawl_delay_seconds_str)
                    crawl_retry_count = int(crawl_retry_count_str)
                except ValueError:
                    st.error("Please enter valid integers for the crawl settings.")
        
        if st.button("Save configuration"):
            document_processors = list(
                map(
                    lambda x: {
                        "document_type": x["document_type"],
                        "chunking": {
                            "strategy": x["chunking_strategy"],
                            "size": x["chunking_size"],
                            "overlap": x["chunking_overlap"],
                        },
                        "loading": {
                            "strategy": x["loading_strategy"],
                        },
                    },
                    edited_document_processors,
                )
            )
            current_config = {
                "prompts": {
                    "condense_question_prompt": "",  # st.session_state['condense_question_prompt'],
                    "answering_prompt": st.session_state["answering_prompt"],
                    "post_answering_prompt": st.session_state["post_answering_prompt"],
                    "enable_post_answering_prompt": st.session_state[
                        "enable_post_answering_prompt"
                    ],
                    "enable_content_safety": st.session_state["enable_content_safety"],
                },
                "messages": {
                    "post_answering_filter": st.session_state[
                        "post_answering_filter_message"
                    ]
                },
                "document_processors": document_processors,
                "logging": {
                    "log_user_interactions": st.session_state["log_user_interactions"],
                    "log_tokens": st.session_state["log_tokens"],
                },
                "orchestrator": {"strategy": st.session_state["orchestrator_strategy"]},
                "crawling": {
                    "crawl_enabled": st.session_state["crawl_enabled"],
                    "crawl_schedule_str": crawl_schedule_str,
                    "crawl_cron": {
                        "seconds": st.session_state["seconds"],
                        "minutes": st.session_state["minutes"],
                        "hours": st.session_state["hours"],
                        "days": st.session_state["days"],
                        "months": st.session_state["months"],
                        "day_of_week": st.session_state["day_of_week"],

                    },
                    "crawl_target_urls": st.session_state["crawl_target_urls"],
                    "crawl_delay_seconds": st.session_state["crawl_delay_seconds"],
                    "crawl_retry_count": st.session_state["crawl_retry_count"],
                }
            }
            ConfigHelper.save_config_as_active(current_config)
            st.success("Configuration saved successfully!")

    except Exception:
        st.error(traceback.format_exc())


if not isLoggedIn():
    parent_dir_path = os.path.join(os.path.dirname(__file__), "..")
    st.switch_page(os.path.join(parent_dir_path, "app.py"))
else:
    main()
