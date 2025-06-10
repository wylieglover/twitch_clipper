
def generate_dynamic_ass_style(target_width: int = 1080, target_height: int = 1920) -> str:
    """
    Generate ASS style template with dynamic resolution.
    Scales font size, margins, and effects based on target resolution.
    """
    # Calculate font size based on resolution (base size for 1080p)
    base_font_size = 52
    font_size = int(base_font_size * (target_width / 1080))
    
    # Calculate margins proportionally
    margin_h = int(30 * (target_width / 1080))
    margin_v = int(500 * (target_height / 1920))
    
    # Calculate outline/shadow proportionally
    outline = round(3.0 * (target_width / 1080), 1)
    shadow = max(2, int(2 * (target_width / 1080))) 
    
    return f"""
            [Script Info]
            ScriptType: v4.00+
            PlayResX: {target_width}
            PlayResY: {target_height}
            ScaledBorderAndShadow: yes

            [V4+ Styles]
            Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
            Style: Default,Arial Black,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

            [Events]
            Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
            """

# Original template for backward compatibility
STYLE_TEMPLATE = """
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2.5,1,2,30,30,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""