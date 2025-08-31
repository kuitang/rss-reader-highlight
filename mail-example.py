"""FrankenUI Mail Example built with MonsterUI (original design by ShadCN)"""

from fasthtml.common import *
from monsterui.all import *
from fasthtml.svg import *
import pathlib, json
from datetime import datetime

app, rt = fast_app(hdrs=Theme.blue.headers())

sidebar_group1 = (('home', 'Inbox', '128'), ('file-text', 'Drafts', '9'), (' arrow-up-right', 'Sent', ''),
    ('ban', 'Junk', '23'), ('trash', 'Trash', ''), ('folder', 'Archive', ''))

sidebar_group2 = (('globe','Social','972'),('info','Updates','342'),('messages-square','Forums','128'),
    ('shopping-cart','Shopping','8'),('shopping-bag','Promotions','21'),)

def MailSbLi(icon, title, cnt): 
    return Li(A(DivLAligned(Span(UkIcon(icon)),Span(title),P(cnt, cls=TextPresets.muted_sm)),href='#',  cls='hover:bg-secondary p-4'))

sidebar = NavContainer(
    NavHeaderLi(H3("Email"), cls='p-3'),
    Li(Select(map(Option, ('alicia@example.com','alicia@gmail.com', 'alicia@yahoo.com')))),
    *[MailSbLi(i, t, c) for i, t, c in sidebar_group1],
    Li(Hr()),
    *[MailSbLi(i, t, c) for i, t, c in sidebar_group2],
    cls='mt-3')

mail_data = json.load(open(pathlib.Path('data_/mail.json')))

def format_date(date_str):
    date_obj = datetime.fromisoformat(date_str)
    return date_obj.strftime("%Y-%m-%d %I:%M %p")

def MailItem(mail):
    cls_base = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2'
    cls = f"{cls_base} {'bg-muted' if mail == mail_data[0] else ''} {'tag-unread' if not mail['read'] else 'tag-mail'}"
    
    return Li(
        DivFullySpaced(
            DivLAligned(
                Strong(mail['name']),
                    Span(cls='flex h-2 w-2 rounded-full bg-blue-600') if not mail['read'] else ''),
                Time(format_date(mail['date']), cls='text-xs')),
            Small(mail['subject'], href=f"#mail-{mail['id']}"),
            Div(mail['text'][:100] + '...', cls=TextPresets.muted_sm),
            DivLAligned(
                *[Label(A(label, href='#'), cls='uk-label-primary' if label == 'work' else '') for label in mail['labels']]),
        cls=cls)

def MailList(mails): return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[MailItem(mail) for mail in mails])

def MailContent():
    return Div(cls='flex flex-col',uk_filter="target: .js-filter")(
        Div(cls='flex px-4 py-2 ')(
            H3('Inbox'),
            TabContainer(Li(A("All Mail",href='#', role='button'),cls='uk-active', uk_filter_control="filter: .tag-mail"), 
                         Li(A("Unread",href='#', role='button'),                   uk_filter_control="filter: .tag-unread"), 
                         alt=True, cls='ml-auto max-w-40', )),
        Div(cls='flex flex-1 flex-col')(
            Div(cls='p-4')(
                Div(cls='uk-inline w-full')(
                    Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                    Input(placeholder='Search'))),
            Div(cls='flex-1 overflow-y-auto max-h-[600px]')(MailList(mail_data))))

def IconNavItem(*d): return [Li(A(UkIcon(o[0],uk_tooltip=o[1]))) for o in d]  
def IconNav(*c,cls=''): return Ul(cls=f'uk-iconnav {cls}')(*c)

def MailDetailView(mail):
    top_icons = [('folder','Archive'), ('ban','Move to junk'), ('trash','Move to trash')]
    reply_icons = [('reply','Reply'), ('reply','Reply all'), ('forward','Forward')]
    dropdown_items = ['Mark as unread', 'Star read', 'Add Label', 'Mute Thread']
    
    return Container(
            DivFullySpaced(
                DivLAligned(
                    DivLAligned(*[UkIcon(o[0],uk_tooltip=o[1]) for o in top_icons]),  
                    Div(UkIcon('clock', uk_tooltip='Snooze'), cls='pl-2'),
                    cls='space-x-2 divide-x divide-border'),
                DivLAligned(
                    *[UkIcon(o[0],uk_tooltip=o[1]) for o in reply_icons],
                    Div(UkIcon('ellipsis-vertical',button=True)),
                    DropDownNavContainer(*map(lambda x: Li(A(x)), dropdown_items)))),
            DivLAligned(
                Span(mail['name'][:2], cls='flex h-10 w-10 items-center justify-center rounded-full bg-muted'),
                Div(Strong(mail['name']),
                    Div(mail['subject']),
                    DivLAligned(P('Reply-To:'), A(mail['email'], href=f"mailto:{mail['email']}"), cls='space-x-1'),
                    P(Time(format_date(mail['date']))),
                    cls='space-y-1'+TextT.sm),
                    cls='m-4 space-x-4'),
            DividerLine(),
            P(mail['text'], cls=TextT.sm +'p-4'),
            DividerLine(),
        Div(TextArea(id='message', placeholder=f"Reply {mail['name']}"),
            DivFullySpaced(
                LabelSwitch('Mute this thread',id='mute'),
                Button('Send', cls=ButtonT.primary)),
            cls='space-y-4'))

@rt
def index():
    return Title("Mail Example"),Container(
        Grid(Div(sidebar, cls='col-span-1'),
             Div(MailContent(), cls='col-span-2'),
             Div(MailDetailView(mail_data[0]), cls='col-span-2'),
             cols_sm=1, cols_md=1, cols_lg=5, cols_xl=5, 
             gap=0, cls='flex-1'),
        cls=('flex', ContainerT.xl))

serve()