from fasthtml.common import *


colors = {
    "primary": "#3498db",
    "secondary": "#2ecc71",
    "background": "#4682B4",  # Light sky blue
    "text": "#333333",  # Darker text for better contrast on light background
    "hover": "#2980b9",
}

custom_style = Style(f"""
    :root {{
        --primary-color: {colors['primary']};
        --secondary-color: {colors['secondary']};
        --background-color: {colors['background']};
        --text-color: {colors['text']};
        --hover-color: {colors['hover']};
    }}
    body {{
        background-color: var(--background-color);
        color: var(--text-color);
        margin: 0;
        padding: 0;
    }}
    .container {{
        max-width: 800px;
        margin: 0 auto;
        padding: 2rem;
        padding-top: 5rem;  /* Increased top padding to accommodate lower logo */
        position: relative;
    }}
    .header {{
        position: absolute;
        top: 10px;  /* Changed from -10px to 10px to move the logo down */
        right: 10px;
    }}
    .logo {{
        width: 140px;
        height: auto;
    }}
    .question-list {{
        display: grid;
        gap: 1rem;
    }}
    .question-item {{
        margin-bottom: 1rem;
    }}
    .question-details {{
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .question-form {{
        display: grid;
        gap: 1.5rem;
    }}
    .form-group {{
        display: grid;
        gap: 0.5rem;
    }}
    .form-group label {{
        font-weight: bold;
    }}
    textarea {{
        width: 100%;
        padding: 0.5rem;
        border: 1px solid #ccc;
        border-radius: 4px;
        background-color: white;
        color: var(--text-color);
    }}
    button {{
        background-color: var(--primary-color);
        color: white;
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }}
    button:hover {{
        background-color: var(--hover-color);
    }}
    .page-title {{
        color: white;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }}
""")