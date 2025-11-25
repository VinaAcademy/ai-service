import pandas as pd


class PassageBuilder:
    @staticmethod
    def build_passages_from_records(df: pd.DataFrame):
        passages = []

        for idx, row in df.iterrows():
            chapter, section, sub_section, content = row
            passage = f"{chapter}\n"

            if section != "":
                passage += f"{section}\n"
            if sub_section != "":
                passage += f"{sub_section}\n"
            if content != "":
                passage += f"{content}"

            passages.append({
                "id": idx + 1,
                "content": content
            })
        return passages
