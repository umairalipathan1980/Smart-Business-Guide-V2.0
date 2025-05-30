import inspect
import re
from typing import Callable, TypeVar

from langchain_core.callbacks.base import BaseCallbackHandler
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.scriptrunner import (add_script_run_ctx,
                                            get_script_run_ctx)

# Code that use as reference to create the callback handler for Streamlit
# https://github.com/shiv248/Streamlit-x-LangGraph-Cookbooks/blob/master/simple_streaming/st_callable_util.py


def get_streamlit_cb(parent_container: DeltaGenerator) -> BaseCallbackHandler:
    """
    Creates a Streamlit callback handler that updates the provided container
    with new tokens in real time.
    """
    class StreamHandler(BaseCallbackHandler):
        def __init__(self, container: DeltaGenerator, initial_text: str = ""):
            self.container = container
            self.token_placeholder = self.container.empty()
            self.text = initial_text
            self.reference_pattern = r'\[(.*?)\]'
            self.is_streaming = False

        # args and kwargs are not used in the following methods, but can be used to pass additional information
        def on_llm_start(self, *args, **kwargs) -> None:
            """Called when the LLM starts generating tokens."""
            self.is_streaming = True

        def on_llm_new_token(self, token: str, **kwargs) -> None:
            """Called for each new token generated by the LLM."""
            if not self.is_streaming:
                return
            self.text += token
            styled_text = re.sub(
                self.reference_pattern,
                r'<span class="reference">[\1]</span>',
                self.text
            )
            try:
                self.token_placeholder.markdown(
                    f"**Assistant:** {styled_text}",
                    unsafe_allow_html=True
                )
            except Exception:
                # If the WebSocket is closed or any error occurs, stop streaming.
                self.is_streaming = False

        def on_llm_end(self, *args, **kwargs) -> None:
            """Called when the LLM finishes generating tokens."""
            self.is_streaming = False

    # Add Streamlit context management to ensure the callback runs in the proper context
    fn_return_type = TypeVar('fn_return_type')

    def add_streamlit_context(fn: Callable[..., fn_return_type]) -> Callable[..., fn_return_type]:
        ctx = get_script_run_ctx()

        def wrapper(*args, **kwargs) -> fn_return_type:
            add_script_run_ctx(ctx=ctx)
            return fn(*args, **kwargs)
        return wrapper

    st_cb = StreamHandler(parent_container)

    # Wrap all callback methods so that they run with the correct Streamlit context
    for method_name, method_func in inspect.getmembers(st_cb, predicate=inspect.ismethod):
        if method_name.startswith('on_'):
            setattr(st_cb, method_name, add_streamlit_context(method_func))

    return st_cb
