from __future__ import annotations

import re
import json
from typing import Union

from agentverse.parser import OutputParser, LLMResult

# from langchain.schema import AgentAction, AgentFinish
from agentverse.utils import AgentAction, AgentFinish

from agentverse.parser import OutputParserError, output_parser_registry


@output_parser_registry.register("recommender")
class RecommenderParser(OutputParser):
    def parse(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        # Find Choice marker
        choice_markers = ['Choice:', 'Choice']
        ans_begin = -1
        for marker in choice_markers:
            try:
                ans_begin = cleaned_output.index(marker) + len(marker)
                break
            except ValueError:
                continue
        if ans_begin == -1:
            print(cleaned_output)
            print("!!!!! Choice not found")
            # Return a default value to avoid crash
            return "unknown", "No explanation found"
        # Find Explanation marker
        explanation_markers = ['Explanation:', 'Explanation']
        ans_end = -1
        rat_begin = -1
        for marker in explanation_markers:
            try:
                ans_end = cleaned_output.index(marker)
                rat_begin = ans_end + len(marker)
                break
            except ValueError:
                continue
        if ans_end == -1 or rat_begin == -1:
            print(cleaned_output)
            print("!!!!! Explanation not found")
            ans = cleaned_output[ans_begin:].strip()
            return ans, "No explanation found"
        ans = cleaned_output[ans_begin:ans_end].strip()
        rat = cleaned_output[rat_begin:].strip()
        if ans == '' or rat == '':
            raise OutputParserError(text)
        return ans, rat

    def parse_backward(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        markers = ['Updated Strategy:', 'Updated Strategy']
        rat_begin = 0
        for marker in markers:
            try:
                rat_begin = cleaned_output.index(marker) + len(marker)
                break
            except ValueError:
                continue
        rat = cleaned_output[rat_begin:].strip()
        return rat


    def parse_summary(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        return cleaned_output.strip()

    def parse_evaluation(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)

        markers = ['Rank:', 'Rank']
        ans_begin = 0
        for marker in markers:
            try:
                ans_begin = cleaned_output.index(marker) + len(marker)
                break
            except ValueError:
                continue
        ans = cleaned_output[ans_begin:].strip().split('\n')
        return ans



@output_parser_registry.register("useragent")
class UserAgentParser(OutputParser):
    def parse(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        return cleaned_output.strip()


    def parse_summary(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        return cleaned_output.strip()

    def parse_update(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        marker = 'My updated self-introduction'
        try:
            rat_begin = cleaned_output.index(marker) + len(marker)
            if cleaned_output[rat_begin] == ':':
                rat_begin += 1
        except ValueError:
            print(cleaned_output)
            rat_begin = 0
        rat = cleaned_output[rat_begin:].strip()
        return rat


@output_parser_registry.register("itemagent")
class ItemAgentParser(OutputParser):
    def parse(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        # Support "CD", "AI method" (legacy), and "scientific concept" markers
        first_markers = ['The updated description of the first CD', 'The updated description of the first AI method', 'The updated description of the first scientific concept']
        second_markers = ['The updated description of the second CD', 'The updated description of the second AI method', 'The updated description of the second scientific concept']
        ans_begin = -1
        for marker in first_markers:
            try:
                ans_begin = cleaned_output.index(marker) + len(marker)
                while ans_begin < len(cleaned_output) and cleaned_output[ans_begin] in ': ':
                    ans_begin += 1
                break
            except ValueError:
                continue
        ans_end = -1
        for marker in second_markers:
            try:
                ans_end = cleaned_output.index(marker)
                break
            except ValueError:
                continue
        rat_begin = -1
        for marker in second_markers:
            try:
                rat_begin = cleaned_output.index(marker) + len(marker)
                while rat_begin < len(cleaned_output) and cleaned_output[rat_begin] in ': ':
                    rat_begin += 1
                break
            except ValueError:
                continue
        if ans_begin == -1 or ans_end == -1 or rat_begin == -1:
            print(f"[ItemAgentParser] Could not parse output, using fallback: {cleaned_output[:200]}")
            # Fallback: split by double newline or return whole text
            parts = cleaned_output.split('\n')
            if len(parts) >= 2:
                return parts[0].strip(), parts[-1].strip()
            return cleaned_output, cleaned_output
        ans = cleaned_output[ans_begin:ans_end].strip()
        rat = cleaned_output[rat_begin:].strip()
        if ans == '' or rat == '':
            print(f"[ItemAgentParser] Empty parsed result, using fallback: {cleaned_output[:200]}")
            parts = cleaned_output.split('\n')
            if len(parts) >= 2:
                return parts[0].strip(), parts[-1].strip()
            return cleaned_output, cleaned_output
        return ans, rat

    def parse_pretrain(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        markers = ['CD Description: ', 'AI method Description: ', 'Scientific concept Description: ']
        ans_begin = 0
        for marker in markers:
            try:
                ans_begin = cleaned_output.index(marker) + len(marker)
                break
            except ValueError:
                continue
        ans = cleaned_output[ans_begin:].strip()
        return ans

    def parse_aug(self, text: LLMResult) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        cleaned_output = re.sub(r"\n+", "\n", cleaned_output)
        markers = ['Speculated CD Reviews: ', 'Speculated AI method Reviews: ', 'Speculated scientific concept Reviews: ']
        ans_begin = 0
        for marker in markers:
            try:
                ans_begin = cleaned_output.index(marker) + len(marker)
                break
            except ValueError:
                continue
        ans = cleaned_output[ans_begin:].strip()
        return ans


