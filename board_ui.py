"""LaunchPad front view. Geometry is in reference-board coordinates (300 x 380)."""
from imgui_bundle import imgui


def style_workbench():
    style = imgui.get_style()
    style.frame_rounding = 5
    style.child_rounding = 8
    style.grab_rounding = 5
    style.frame_padding = (9, 5)
    style.item_spacing = (8, 6)
    for slot, rgb in ((imgui.Col_.window_bg, (16, 23, 31)),
                      (imgui.Col_.child_bg, (23, 32, 43)),
                      (imgui.Col_.frame_bg, (32, 46, 59)),
                      (imgui.Col_.button, (43, 65, 81)),
                      (imgui.Col_.button_hovered, (49, 90, 105)),
                      (imgui.Col_.button_active, (31, 105, 111)),
                      (imgui.Col_.text, (231, 238, 244)),
                      (imgui.Col_.text_disabled, (159, 178, 192))):
        style.set_color_(slot, tuple(v / 255 for v in rgb) + (1,))


# Opaque ImGui U32 colors (least significant byte = red).
def rgb(value):
    return 0xff000000 | ((value & 255) << 16) | (value & 0xff00) | (value >> 16)


SILK = rgb(0xffebda)
TIN = rgb(0xc1bcb0)
GOLD = rgb(0xe3ba78)
BODY = rgb(0x292729)
DARK = rgb(0x19191c)


class BoardFace:
    def __init__(self, x, y, scale):
        self.x, self.y, self.s = x, y, scale
        self.d = imgui.get_window_draw_list()

    def pt(self, x, y):
        return self.x + x*self.s, self.y + y*self.s

    def rect(self, x, y, w, h, color, radius=0):
        self.d.add_rect_filled(self.pt(x, y), self.pt(x+w, y+h), color, radius*self.s)

    def dot(self, x, y, r, color):
        self.d.add_circle_filled(self.pt(x, y), r*self.s, color)

    def text(self, x, y, label, size=10, color=SILK):
        self.d.add_text(imgui.get_font(), size*self.s, self.pt(x, y), color, label)

    def package(self, cx, cy, side, pins):
        half = side/2
        for i in range(pins):
            d = -half+3+i*(side-6)/(pins-1)
            for sign in (-1, 1):
                self.rect(cx+d-0.7, cy+sign*half-3, 1.4, 6, TIN)
                self.rect(cx+sign*half-3, cy+d-0.7, 6, 1.4, TIN)
        self.rect(cx-half, cy-half, side, side, BODY, 3)
        self.dot(cx-half+5, cy-half+5, 1.8, rgb(0x99918b))

    def tactile(self, cx, cy, side, pressed=False):
        r = side/2
        for dx in (-r, r-4):
            self.rect(cx+dx, cy-r-2, 4, side+4, TIN, 1)
        self.rect(cx-r, cy-r+2, side, side, DARK, 3)
        self.rect(cx-r, cy-r, side, side, rgb(0xb6a894), 3)
        for dx, dy in ((-1,-1), (1,1), (-1,1), (1,-1)):
            self.dot(cx+dx*(r-3), cy+dy*(r-3), 1.3, BODY)
        self.dot(cx, cy+1, side*.31, DARK)
        self.dot(cx, cy+(1 if pressed else -1.6), side*.27, rgb(0x242326 if pressed else 0x474448))

    def user_switch(self, cx, name, pin):
        imgui.set_cursor_screen_pos(self.pt(cx-23, 326))
        imgui.invisible_button(f'{name} ({pin})', (46*self.s, 48*self.s), imgui.ButtonFlags_.enable_nav)
        down = imgui.is_item_active()
        hover = imgui.is_item_hovered()
        if hover or imgui.is_item_focused():
            self.d.add_rect(self.pt(cx-22, 326), self.pt(cx+22, 374), SILK, 4*self.s)
        if hover:
            imgui.set_mouse_cursor(imgui.MouseCursor_.hand)
            imgui.set_tooltip(f'{name} / {pin}  |  ' + ('Pressed: LOW' if down else 'Hold to press'))
        self.text(cx-17, 327, name, 10)
        self.tactile(cx, 354, 32, down)
        return down

    def static_parts(self):
        self.rect(0, 0, 300, 380, rgb(0xb81737), 5)
        for cx in (12, 288):
            for cy in (12, 368):
                self.dot(cx, cy, 7, TIN)
                self.dot(cx, cy, 5, rgb(0x19232d))
        # Debug probe, micro USB, test pads and isolation jumpers, above target.
        self.rect(32, 0, 43, 25, TIN, 2)
        self.rect(36, 0, 35, 7, BODY, 2)
        self.rect(40, 1, 27, 2, rgb(0xe7ded0))
        self.package(108, 46, 24, 8)
        self.d.add_quad_filled(self.pt(217,47), self.pt(249,79), self.pt(217,111), self.pt(185,79), BODY)
        for i in range(7):
            self.dot(183+13*i, 13, 4.5, GOLD)
            self.dot(183+13*i, 13, 3, rgb(0x86233a))
        for x,y in ((33,49),(60,66),(40,87),(83,101),(133,26),(155,48),(182,40),(242,43),
                     (122,215),(111,290),(182,306),(93,250),(200,286),(192,217)):
            self.rect(x,y,9,4,TIN,1)
            self.rect(x+2,y,5,4,rgb(0xb29072))
        self.text(25, 125, 'RESET', 9)
        self.text(80, 125, 'BSL', 9)
        self.tactile(43, 154, 27)
        self.tactile(94, 154, 27)
        self.text(144, 109, 'DEBUG ISOLATION', 9)
        self.rect(142, 123, 124, 27, SILK, 2)
        for i in range(9):
            self.rect(144+i*13.5, 125, 11, 23, BODY, 1)
            self.rect(147+i*13.5, 128, 4, 6, GOLD, 1)
        self.text(79, 174, 'MSP-EXP430F5529LP', 14)
        # Two double-row, ten-position headers flank the target MCU.
        for x, label in ((26, 'J1 / J3'), (254, 'J4 / J2')):
            self.text(x-4, 190, label, 9)
            for i in range(10):
                for dx in (0, 13):
                    self.rect(x+dx-4, 202+i*12, 9, 9, rgb(0x822038), 2)
                    self.dot(x+dx+.5, 206+i*12, 3.3, GOLD)
                    self.dot(x+dx+.5, 206+i*12, 2, DARK)
        self.package(150, 249, 60, 18)
        self.text(127, 235, 'MSP430', 13)
        self.text(131, 251, 'F5529', 13)
        self.text(120, 298, 'LaunchPad', 14)
        self.rect(144, 348, 13, 30, SILK, 1)
        self.rect(146, 350, 9, 26, BODY, 1)
        self.rect(148, 353, 5, 5, GOLD)


def draw_board(model):
    imgui.separator_text('LaunchPad')
    p = imgui.get_cursor_screen_pos()
    available = max(1, imgui.get_content_region_avail().x)
    width = min(available, 350)
    face = BoardFace(p.x+(available-width)/2, p.y, width/300)
    face.static_parts()
    model.s1 = face.user_switch(81, 'PUSH1', 'P2.1')
    model.s2 = face.user_switch(218, 'PUSH2', 'P1.1')
    r = model.memory[:] if model.memory is not None else bytes(14)
    for cx, pin, on, lit, off in ((124, 'P1.0', r[0]&r[1]&1, 0xff5349, 0x611829),
                                  (176, 'P4.7', r[8]&r[9]&128, 0x65ff84, 0x23492e)):
        face.text(cx-11, 345, pin, 9)
        face.rect(cx-5, 362, 10, 10, TIN, 2)
        face.dot(cx, 367, 6 if on else 4, rgb(lit if on else off))
        if on:
            face.dot(cx-1, 366, 2, rgb(0xfff5d6))
    imgui.set_cursor_screen_pos((p.x, p.y+380*face.s))
    imgui.dummy((width, 1))
    imgui.text_disabled('PUSH1: P2.1   /   PUSH2: P1.1')
