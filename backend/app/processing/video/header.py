import tempfile
import skia

EMOJI_CHARS = set('😂🔥💯‼️❗⁉️😱🚨🎮🏆💪👍❤️🤔😍🙌🔴⚡🎯🚀💎🎊🎉'
                  '😎🤑🤩🥳😭😢😅🤣😊😁😃😄😆😋😜😝🤪🤨🧐🤓'
                  '😏🤤🤗🤭🤫🤐🤬😡😠🤯😵‍💫😴😪🤢🤮🤧🤒🤕'
                  '🥺😌😔😞😓😟😰😨😧😦😮😯😲🤯😳🥴🤠'
                  '🤡👺👹👻💀☠️👽👾🤖🎃😺😸😹😻😼😽🙀😿😾'
                  '🙈🙉🙊💋💌💘💝💖💗💓💞💕💟❣️💔❤️‍🔥❤️‍🩹'
                  '🧡💛💚💙💜🤎🖤🤍💢💥💫💦💨🕳️💬💭🗯️💤'
                  '👋🤚🖐️✋🖖👌🤏✌️🤞🤟🤘🤙👈👉👆🖕👇☝️'
                  '👍👎👊✊🤛🤜👏🙌👐🤲🤝🙏✍️💅🤳💪🦾🦿🦵🦶'
                  '👂🦻👃🧠🦷🦴👀👁️👅👄👶🧒👦👧🧑👱'
                  '👨👩🧔👴👵🙍🙎🙅🙆💁🙋🧏🙇🤦🤷👮🕵️💂👷'
                  '🤴👸👳👲🧕🤵👰🤰🤱👼🎅🤶🦸🦹🧙🧚🧛🧜🧝🧞🧟'
                  '💆💇🚶🧍🧎🏃💃🕺🤺🏇⛷️🏂🏌️🏄🚣🏊⛹️🏋️🚴🤸🤼🤽🤾🤹'
                  '🧘🛀🛌☕🎭🎨🎬🎤🎧🎼🎵🎶🎹🥁🎷🎺🎸🪕🎻🎲🎯🎳🎮🎰🧩'
                  '🚗🚕🚙🚌🚎🏎️🚓🚑🚒🚐🚚🚛🚜🏍️🛵🚲🛴🛹🚁🛸🚀✈️🛩️🛫🛬'
                  '⭐🌟💫⚡☄️💥🔥🌈☀️🌤️⛅🌦️🌧️⛈️🌩️🌨️❄️☃️⛄🌪️💨💧💦☔⚽🏀🏈⚾🥎🎾🏐🏉🥏'
                  '🎱🪀🏓🏸🏒🏑🥍🏏🥅⛳🪁🏹🎣🤿🥊🥋🎽🛹🛷⛸️🥌🎿⛷️🏂🪂🏋️🤸🤺🤼🤽🤾🤹'
                  '🍔🍟🍕🌭🥪🌮🌯🥙🧆🥚🍳🥘🍲🥗🍿🧈🥞🧇🥓🥩🍗🍖🦴🌭🍔🍟🍕')

def draw_text_with_emojis(canvas, text, x, y, primary_font, emoji_font, paint):
    """Draw text with proper emoji handling"""
    current_x = x
    
    for char in text:
        if char in EMOJI_CHARS and emoji_font:
            # Draw emoji with emoji font
            emoji_font_obj = skia.Font()
            emoji_font_obj.setSize(primary_font.getSize())
            emoji_font_obj.setTypeface(emoji_font)
            
            canvas.drawString(char, current_x, y, emoji_font_obj, paint)
            char_width = emoji_font_obj.measureText(char)
        else:
            # Draw regular character with primary font
            canvas.drawString(char, current_x, y, primary_font, paint)
            char_width = primary_font.measureText(char)
        
        current_x += char_width
    
    return current_x - x  # Return total width

def measure_text_with_emojis(text, primary_font, emoji_font):
    """Measure text width accounting for emojis"""
    total_width = 0

    for char in text:
        if char in EMOJI_CHARS and emoji_font:
            emoji_font_obj = skia.Font()
            emoji_font_obj.setSize(primary_font.getSize())
            emoji_font_obj.setTypeface(emoji_font)
            char_width = emoji_font_obj.measureText(char)
        else:
            char_width = primary_font.measureText(char)
        total_width += char_width
    
    return total_width

def get_apple_emoji_font():
    """Get Apple Color Emoji font - prioritize local file"""
    
    # Try to load your downloaded Apple Color Emoji font first
    local_font_paths = [
        "fonts/AppleColorEmoji.ttf", 
    ]
    
    # Try local Apple Color Emoji file first
    for font_path in local_font_paths:
        try:
            typeface = skia.Typeface.MakeFromFile(font_path)
            if typeface:
                print(f"Successfully loaded Apple Color Emoji from: {font_path}")
                return typeface
        except Exception as e:
            print(f"Could not load {font_path}: {e}")
            continue
    
    # Fallback to system fonts
    font_mgr = skia.FontMgr()
    
    # Try system emoji fonts
    system_emoji_fonts = [
        "Apple Color Emoji",  # If somehow available on Windows
        "Segoe UI Emoji",     # Windows default
        "Noto Color Emoji",   # Google
        "EmojiOne Color",     # Alternative
    ]
    
    for font_name in system_emoji_fonts:
        try:
            typeface = font_mgr.matchFamilyStyle(font_name, skia.FontStyle.Normal())
            if typeface:
                print(f"Using system emoji font: {font_name}")
                return typeface
        except Exception as e:
            print(f"Could not load system font {font_name}: {e}")
            continue
    
    print("Warning: No emoji font found - emojis may not display correctly")
    return None

def create_text_overlay_image(text: str, video_width: int, video_height: int) -> str:
    """Create a TikTok-style overlay PNG with Apple emoji support using Skia"""
    
    # Create surface
    surface = skia.Surface(video_width, video_height)
    canvas = surface.getCanvas()
    canvas.clear(skia.Color(0, 0, 0, 0))  # Transparent background
    
    # Font setup
    font_size = max(32, int(video_width * 0.045))
    
    # Load fonts
    font_mgr = skia.FontMgr()
    
    # Primary font
    try:
        primary_typeface = font_mgr.matchFamilyStyle("Impact", skia.FontStyle.Bold())
        if not primary_typeface:
            primary_typeface = font_mgr.matchFamilyStyle("Arial", skia.FontStyle.Bold())
    except:
        primary_typeface = font_mgr.matchFamilyStyle("Arial", skia.FontStyle.Normal())
    
    # Get Apple emoji font
    emoji_typeface = get_apple_emoji_font()
    
    # Create font with primary typeface
    font = skia.Font()
    font.setSize(font_size)
    font.setTypeface(primary_typeface)
    
    # Text paint
    text_paint = skia.Paint()
    text_paint.setAntiAlias(True)
    text_paint.setColor(skia.Color(0, 0, 0, 255))  # Black text
    
    # Background paint
    bg_paint = skia.Paint()
    bg_paint.setAntiAlias(True)
    bg_paint.setColor(skia.Color(255, 255, 255, 240))  # White with slight transparency
    
    # Text wrapping function
    def wrap_text(txt, max_width):
        words = txt.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            text_width = measure_text_with_emojis(test_line, font, emoji_typeface)
            
            if text_width <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
            
            if len(lines) == 3:
                break
        
        if current_line and len(lines) < 3:
            lines.append(' '.join(current_line))
        
        # Add ellipsis if text was truncated
        if len(lines) == 3 and ' '.join(words) != ' '.join(lines):
            lines[-1] += "…"
        
        return lines
    
    # Wrap text
    max_text_width = int(video_width * 0.85)
    lines = wrap_text(text, max_text_width)
    
    # Calculate metrics
    font_metrics = font.getMetrics()
    line_height = abs(font_metrics.fDescent - font_metrics.fAscent)
    
    # Padding and spacing
    pad_x = max(12, int(font_size * 0.4))
    pad_y = max(8, int(font_size * 0.25))
    line_space = max(6, int(font_size * 0.2))
    corner_radius = max(6, int(font_size * 0.2))
    
    # Starting position
    y = 250
    
    # Draw each line
    for line in lines:
        if not line.strip():
            continue
            
        # Measure text with emoji support
        text_width = measure_text_with_emojis(line, font, emoji_typeface)
        
        # Calculate background dimensions
        bg_width = text_width + pad_x * 2
        bg_height = line_height + pad_y * 2
        bg_x = (video_width - bg_width) / 2
        bg_y = y
        
        # Draw rounded rectangle background
        bg_rect = skia.RRect.MakeRectXY(
            skia.Rect.MakeXYWH(bg_x, bg_y, bg_width, bg_height),
            corner_radius, corner_radius
        )
        canvas.drawRRect(bg_rect, bg_paint)
        
        # Calculate text position
        text_x = bg_x + pad_x
        text_y = bg_y + pad_y - font_metrics.fAscent
        
        # Draw text with emoji support
        draw_text_with_emojis(canvas, line, text_x, text_y, font, emoji_typeface, text_paint)
        
        # Move to next line
        y += bg_height + line_space
    
    # Save to file
    image = surface.makeImageSnapshot()
    out_path = tempfile.mktemp(suffix='.png')
    image.save(out_path, skia.kPNG)
    
    return out_path