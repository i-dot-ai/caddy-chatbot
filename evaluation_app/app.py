from dataclasses import dataclass, field
import os
from typing import Dict
import logging
import uuid


import boto3
from dotenv import load_dotenv
from requests_aws4auth import AWS4Auth
from fasthtml.common import *

from styling import custom_style

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
session = boto3.Session()
boto3.setup_default_session(region_name="eu-west-2")
dynamodb = boto3.resource("dynamodb")


db = database("data/users.db")
todos, users = db.t.todos, db.t.users
if todos not in db.t:
    users.create(dict(name=str, pwd=str), pk="name")
    todos.create(
        id=int, title=str, done=bool, name=str, details=str, priority=int, pk="id"
    )
Todo, User = todos.dataclass(), users.dataclass()
login_redir = RedirectResponse("/login", status_code=303)


def before(req, sess):
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return login_redir
    todos.xtra(name=auth)


bware = Beforeware(before, skip=[r"/favicon\.ico", r"/static/.*", r".*\.css", "/login"])


def before(req, sess):
    auth = req.scope["auth"] = sess.get("auth", None)
    if not auth:
        return login_redir
    todos.xtra(name=auth)


app, rt = fast_app(before=bware, hdrs=[custom_style])


@dataclass
class Question:
    id: int
    text: str
    sub_questions: str = ""
    useful_info: str = ""
    useful_links: str = ""


@dataclass
class Database:
    questions: Dict[int, Question] = field(default_factory=dict)
    question_counter: int = 0

    def update_question(
        self, id: int, sub_questions: str, useful_info: str, useful_links: str
    ) -> Question:
        if id in self.questions:
            self.questions[id].sub_questions = sub_questions
            self.questions[id].useful_info = useful_info
            self.questions[id].useful_links = useful_links
            return self.questions[id]
        return None


@rt("/login")
def get():
    frm = Form(
        Input(id="name", placeholder="Name"),
        Input(id="pwd", type="password", placeholder="Password"),
        Button("login"),
        action="/login",
        method="post",
    )
    return Titled("Login", frm)


@dataclass
class Login:
    name: str
    pwd: str


@rt("/login")
def post(login: Login, sess):
    if not login.name or not login.pwd:
        return login_redir
    try:
        u = users[login.name]
    except NotFoundError:
        u = users.insert(login)
    if not compare_digest(u.pwd.encode("utf-8"), login.pwd.encode("utf-8")):
        return login_redir
    sess["auth"] = u.name
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(sess):
    del sess["auth"]
    return login_redir


db = Database()
question_table = dynamodb.Table("Evaluation-Questions")
questions = question_table.scan()
for q in questions['Items']:
    db.questions[int(q["QuestionId"])] = Question(id=int(q["QuestionId"]), text=q['QuestionString'])

id_curr = "current-question"


def qid(id):
    return f"question-{id}"


@patch
def __ft__(self: Question):
    show = AX(self.text, f"/questions/{self.id}", f"question-details-{self.id}")
    details = Div(id=f"question-details-{self.id}", cls="question-details")
    return Li(show, details, id=qid(self.id), cls="question-item")


@rt("/")
def get():
    card = Card(
        Ul(*db.questions.values(), id="question-list", cls="question-list"),
    )
    title = "Advisor Questions"

    header = Div(Img(src="Citizens_Advice_logo.png", cls="logo"), cls="header")

    return Title(title), Main(
        header,
        H1(
            title,
            style="text-align: center; margin-top: 2rem; margin-bottom: 2rem;",
            cls="page-title",
        ),
        card,
        cls="container",
    )


@rt("/questions/{id}")
def get(id: int, sess):
    question = db.questions.get(id)
    if not question:
        return "Question not found", 404

    form = Form(
        H2(question.text, style="margin-bottom: 1.5rem;"),
        Div(
            Div(
                Label("What Questions would you ask?", for_="sub_questions"),
                Textarea(
                    id="sub_questions",
                    name="sub_questions",
                    rows=5,
                    value=question.sub_questions,
                ),
                cls="form-group",
            ),
            Div(
                Label("Useful Information", for_="useful_info"),
                Textarea(
                    id="useful_info",
                    name="useful_info",
                    rows=5,
                    value=question.useful_info,
                ),
                cls="form-group",
            ),
            Div(
                Label("Useful Links", for_="useful_links"),
                Textarea(
                    id="useful_links",
                    name="useful_links",
                    rows=5,
                    value=question.useful_links,
                ),
                cls="form-group",
            ),
            cls="question-form",
        ),
        Button("Save", style="justify-self: start;"),
        hx_post=f"/questions/{id}/update",
        hx_target=f"#question-details-{id}",
    )

    return form


@rt("/questions/{id}/update")
def post(id: int, sub_questions: str, useful_info: str, useful_links: str, sess):
    answer_table = dynamodb.Table("Evaluation-Answers")
    answer_table.put_item(
        Item={
            "AnswerId": str(uuid.uuid4()), 
            "UserName": str(sess["auth"]),
            "QuestionId": id,
            "FollowOnQuestions": str(sub_questions),
            "UsefulInfo": str(useful_info),
            "UsefulLinks": str(useful_links),
        }
    )
    pass

logger.info("Starting application...")
logger.info(f"AWS_ACCESS_KEY_ID is {'set' if os.getenv('AWS_ACCESS_KEY_ID') else 'not set'}")
logger.info(f"AWS_SECRET_ACCESS_KEY is {'set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'not set'}")
logger.info(f"AWS_REGION is set to: {os.getenv('AWS_REGION', 'not set')}")
if __name__ == "__main__":
    logger.info("Entering main execution block")
    serve(host="0.0.0.0", port=8080)
