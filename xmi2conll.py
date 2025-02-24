import os
import xml.etree.ElementTree as ET
import argparse
import re
import json
from xmi2json import extract_tokens_from_xmi, extract_custom_annos, map_tokens_to_spans


def extract_sofa_string(xmi_content):
    """
    Extracts the full text (sofaString) from the XMI file.
    """
    root = ET.fromstring(xmi_content)
    sofa_element = root.find(".//{http:///uima/cas.ecore}Sofa")
    return sofa_element.get("sofaString") if sofa_element is not None else ""


def convert_to_conll(xmi_content, ners_spans):
    """
    Converts extracted NER spans and the original XMI text into CoNLL format.

    :param xmi_content: The XML content of the original XMI file.
    :param ners_spans: A dictionary mapping XMI IDs to span details.
    :return: CoNLL-formatted string.
    """
    text = extract_sofa_string(xmi_content)
    tokens = text.split()  # Tokenize by whitespace
    conll_output = []

    # Track token positions
    current_index = 0
    token_data = []

    # Build token mapping with character offsets
    for token in tokens:
        start_index = text.find(token, current_index)
        end_index = start_index + len(token)
        token_data.append((token, start_index, end_index))
        current_index = end_index  # Update index for next search

    # Assign BIO tags
    token_labels = {t[1]: "O" for t in token_data}  # Default to "O"

    for span in ners_spans.values():
        label = span["label"]
        begin, end = span["begin"], span["end"]

        # Assign "B-Label" for the first token, "I-Label" for the rest
        inside_entity = False
        for token, start_idx, end_idx in token_data:
            if start_idx >= begin and end_idx <= end:
                if not inside_entity:
                    token_labels[start_idx] = f"B-{label}"
                    inside_entity = True
                else:
                    token_labels[start_idx] = f"I-{label}"

    # Generate CoNLL output
    for token, start_idx, end_idx in token_data:
        conll_output.append(f"{token} {start_idx} {end_idx} {token_labels[start_idx]}")

    return "\n".join(conll_output)


def process_xmi_to_conll(xmi_path, output_dir):
    """
    Processes an XMI file, extracts annotations, and converts them to CoNLL format.
    Saves the output file in the specified directory.
    """
    if not os.path.exists(xmi_path):
        print(f"Error: XMI file not found at {xmi_path}")
        return

    with open(xmi_path, "r", encoding="utf-8") as xmi_file:
        xmi_content = xmi_file.read()

    file_name = os.path.splitext(os.path.basename(xmi_path))[0]  # Extract base name
    tokens, token_lookup = extract_tokens_from_xmi(xmi_content)
    ners, relations = extract_custom_annos(xmi_content)

    ners_spans = map_tokens_to_spans(tokens, token_lookup, ners)
    conll_data = convert_to_conll(xmi_content, ners_spans)

    os.makedirs(output_dir, exist_ok=True)
    output_conll_path = os.path.join(output_dir, f"{file_name}.conll")

    with open(output_conll_path, "w", encoding="utf-8") as f:
        f.write(conll_data)

    print(f"Processed: {xmi_path}")
    print(f"Saved CoNLL file to {output_conll_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert an XMI file into CoNLL format.")
    parser.add_argument("xmi_path", type=str, help="Path to the input XMI file.")
    parser.add_argument(
        "--output_dir", type=str, default=None,
        help="Directory to save the CoNLL file. Defaults to the same directory as the input XMI file."
    )

    args = parser.parse_args()
    output_directory = args.output_dir if args.output_dir else os.path.abspath(os.path.dirname(args.xmi_path) or ".")

    process_xmi_to_conll(args.xmi_path, output_directory)
