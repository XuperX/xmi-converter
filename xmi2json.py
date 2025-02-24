import json
import xml.etree.ElementTree as ET
import re
import os
import argparse

def extract_tokens_from_xmi(xmi_content):
    """
    Extracts token information from an XMI string.
    Returns a dictionary mapping (begin, end) -> token information.
    """
    root = ET.fromstring(xmi_content)
    sofa_element = root.find(".//{http:///uima/cas.ecore}Sofa")
    sofa_text = sofa_element.get("sofaString") if sofa_element is not None else ""

    tokens = []
    token_lookup = {}

    for token in root.findall(".//{http:///de/tudarmstadt/ukp/dkpro/core/api/segmentation/type.ecore}Token"):
        xmi_id = token.get("xmi:id")
        begin = int(token.get("begin"))
        end = int(token.get("end"))
        token_text = sofa_text[begin:end].strip()
        token_text = re.sub(r'\s+', ' ', token_text)

        if not token_text:
            continue

        tokens.append({"xmi_id": xmi_id, "begin": begin, "end": end, "token": token_text})
        token_lookup[(begin, end)] = token_text

    return tokens, token_lookup

def extract_custom_annos(xmi_content):
    """
    Extracts custom annotations (NER spans and relationships) from an XMI string.
    """
    annos = {}
    
    for xmi_line in xmi_content.split("\n"):
        label_pattern = r"<custom\d?:(\w+)"
        xmi_id_pattern = r'xmi:id="(\d+)"'
        begin_pattern = r'begin="(\d+)"'
        end_pattern = r'end="(\d+)"'
        attribute_pattern = r'(\w+)="([^"]+)"'

        label_match = re.search(label_pattern, xmi_line)
        xmi_id_match = re.search(xmi_id_pattern, xmi_line)
        begin_match = re.search(begin_pattern, xmi_line)
        end_match = re.search(end_pattern, xmi_line)

        if label_match and xmi_id_match and begin_match and end_match:
            anno_data = {
                "xmi_id": xmi_id_match.group(1),
                "begin": int(begin_match.group(1)),
                "end": int(end_match.group(1)),
                "label": label_match.group(1),
            }

            attributes = re.findall(attribute_pattern, xmi_line)
            for attr_name, attr_value in attributes:
                if attr_name not in ["xmi:id", "begin", "end", "sofa"]:
                    anno_data[attr_name] = attr_value

            annos[anno_data["xmi_id"]] = anno_data

    ners = {k: v for k, v in annos.items() if "Dependent" not in v and "Governor" not in v}
    relations = {k: v for k, v in annos.items() if "Dependent" in v and "Governor" in v}

    return ners, relations

def map_tokens_to_spans(tokens, token_lookup, spans):
    """
    Maps tokens to annotated spans using (begin, end) index.
    """
    for span in spans.values():
        span_tokens = [token["token"] for token in tokens if span["begin"] <= token["begin"] <= span["end"]]
        span["token"] = " ".join(span_tokens) if span_tokens else "UNKNOWN"
    return spans

def map_relationships(relations, ners):
    """
    Maps relationships between spans using their XMI IDs.
    """
    relationships = []
    for rel in relations.values():
        relationships.append({
            "xmi_id": rel["xmi_id"],
            "label": rel["label"],
            "rel_dep": ners.get(rel.get("Dependent"), {}).get("token", "UNKNOWN"),
            "rel_gov": ners.get(rel.get("Governor"), {}).get("token", "UNKNOWN"),
        })
    return relationships

def process_xmi_file(xmi_path):
    """
    Processes an XMI file and extracts tokens, NER spans, and relationships.
    Saves output as JSON in the same directory as the XMI file.
    """
    if not os.path.exists(xmi_path):
        print(f"Error: XMI file not found at {xmi_path}")
        return

    with open(xmi_path, "r", encoding="utf-8") as xmi_file:
        xmi_content = xmi_file.read()

    file_name = os.path.splitext(os.path.basename(xmi_path))[0]
    output_dir = os.path.dirname(xmi_path)
    
    tokens, token_lookup = extract_tokens_from_xmi(xmi_content)
    ners, relations = extract_custom_annos(xmi_content)

    ners_spans = map_tokens_to_spans(tokens, token_lookup, ners)
    relationships = map_relationships(relations, ners_spans)

    output_ner_path = os.path.join(output_dir, f"{file_name}_ner.json")
    output_rel_path = os.path.join(output_dir, f"{file_name}_rel.json")

    with open(output_ner_path, "w", encoding="utf-8") as f:
        json.dump(ners_spans, f, ensure_ascii=False, indent=4)

    with open(output_rel_path, "w", encoding="utf-8") as f:
        json.dump(relationships, f, ensure_ascii=False, indent=4)

    print(f"Processed: {xmi_path}")
    print(f"Saved NER annotations to {output_ner_path}")
    print(f"Saved Relationships to {output_rel_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract tokens, NER annotations, and relationships from an XMI file.")
    parser.add_argument("xmi_path", type=str, help="Path to the input XMI file.")
    args = parser.parse_args()
    process_xmi_file(args.xmi_path)
