import os
import zipfile
import fitz


def safe_filename(name: str) -> str:
    return (
        name.replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace("*", "")
        .replace("?", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
        .strip()
    )


def split_pdf(
    input_path: str,
    sections: list[dict],
    output_dir: str,
    client_name: str = "",
) -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)

    original = fitz.open(input_path)
    outputs = []

    safe_client_name = safe_filename(client_name)

    for section in sections:
        category = section["category"] or "Unknown"
        safe_category = safe_filename(category)

        if safe_client_name:
            filename = f"{safe_client_name} - {safe_category}.pdf"
        else:
            filename = (
                f"{safe_category}_pages_"
                f"{section['startPage']}-{section['endPage']}.pdf"
            )

        output_path = os.path.join(output_dir, filename)

        new_pdf = fitz.open()

        for page_num in section["pages"]:
            new_pdf.insert_pdf(
                original,
                from_page=page_num - 1,
                to_page=page_num - 1,
            )

        new_pdf.save(output_path)
        new_pdf.close()

        outputs.append(
            {
                "category": category,
                "filename": filename,
                "path": output_path,
                "startPage": section["startPage"],
                "endPage": section["endPage"],
            }
        )

    original.close()
    return outputs


def create_zip(files: list[dict], zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            zipf.write(file["path"], arcname=file["filename"])

    return zip_path