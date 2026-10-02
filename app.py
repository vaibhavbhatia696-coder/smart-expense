from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = "smart-expense-secret-key-change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expense_manager.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "warning"
login_manager.init_app(app)


# =========================================================
# DATABASE MODELS
# =========================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    expenses = db.relationship(
        "Expense",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    incomes = db.relationship(
        "Income",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    budgets = db.relationship(
        "Budget",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    amount = db.Column(db.Float, nullable=False)

    category = db.Column(
        db.String(50),
        nullable=False
    )

    description = db.Column(
        db.String(255)
    )

    payment_method = db.Column(
        db.String(50),
        default="Cash"
    )

    date = db.Column(
        db.Date,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    amount = db.Column(db.Float, nullable=False)

    source = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(255)
    )

    date = db.Column(
        db.Date,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    month = db.Column(
        db.String(7),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "month",
            "user_id",
            name="unique_user_month_budget"
        ),
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =========================================================
# AUTHENTICATION
# =========================================================

@app.route("/")
def home():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not name or not email or not password:
            flash(
                "All fields are required.",
                "danger"
            )
            return redirect(url_for("register"))

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "danger"
            )
            return redirect(url_for("register"))

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:
            flash(
                "Email already registered.",
                "warning"
            )
            return redirect(url_for("login"))

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        flash(
            "Account created successfully. Please login.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    total_income = db.session.query(
        func.coalesce(
            func.sum(Income.amount),
            0
        )
    ).filter(
        Income.user_id == current_user.id
    ).scalar()

    total_expense = db.session.query(
        func.coalesce(
            func.sum(Expense.amount),
            0
        )
    ).filter(
        Expense.user_id == current_user.id
    ).scalar()

    balance = total_income - total_expense

    current_month = datetime.now().strftime("%Y-%m")

    current_budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month
    ).first()

    budget_amount = (
        current_budget.amount
        if current_budget
        else 0
    )

    monthly_expense = db.session.query(
        func.coalesce(
            func.sum(Expense.amount),
            0
        )
    ).filter(
        Expense.user_id == current_user.id,
        func.strftime(
            "%Y-%m",
            Expense.date
        ) == current_month
    ).scalar()

    remaining_budget = budget_amount - monthly_expense

    recent_expenses = Expense.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Expense.date.desc()
    ).limit(5).all()

    category_data = db.session.query(
        Expense.category,
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == current_user.id
    ).group_by(
        Expense.category
    ).all()

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        budget_amount=budget_amount,
        monthly_expense=monthly_expense,
        remaining_budget=remaining_budget,
        recent_expenses=recent_expenses,
        category_data=category_data
    )


# =========================================================
# EXPENSES
# =========================================================

@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():

    if request.method == "POST":

        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get(
            "description"
        )
        payment_method = request.form.get(
            "payment_method"
        )
        date_string = request.form.get("date")

        try:
            amount = float(amount)

            if amount <= 0:
                raise ValueError

            expense_date = datetime.strptime(
                date_string,
                "%Y-%m-%d"
            ).date()

        except (ValueError, TypeError):
            flash(
                "Please enter valid expense details.",
                "danger"
            )
            return redirect(
                url_for("expenses")
            )

        expense = Expense(
            amount=amount,
            category=category,
            description=description,
            payment_method=payment_method,
            date=expense_date,
            user_id=current_user.id
        )

        db.session.add(expense)
        db.session.commit()

        flash(
            "Expense added successfully.",
            "success"
        )

        return redirect(
            url_for("expenses")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    category_filter = request.args.get(
        "category",
        ""
    ).strip()

    query = Expense.query.filter_by(
        user_id=current_user.id
    )

    if search:

        query = query.filter(
            Expense.description.ilike(
                f"%{search}%"
            )
            |
            Expense.category.ilike(
                f"%{search}%"
            )
        )

    if category_filter:

        query = query.filter_by(
            category=category_filter
        )

    all_expenses = query.order_by(
        Expense.date.desc()
    ).all()

    return render_template(
        "expenses.html",
        expenses=all_expenses
    )


@app.route("/expense/delete/<int:id>")
@login_required
def delete_expense(id):

    expense = Expense.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(expense)
    db.session.commit()

    flash(
        "Expense deleted.",
        "success"
    )

    return redirect(
        url_for("expenses")
    )


# =========================================================
# INCOME
# =========================================================

@app.route("/income", methods=["GET", "POST"])
@login_required
def income():

    if request.method == "POST":

        amount = request.form.get("amount")
        source = request.form.get("source")
        description = request.form.get(
            "description"
        )
        date_string = request.form.get("date")

        try:

            amount = float(amount)

            if amount <= 0:
                raise ValueError

            income_date = datetime.strptime(
                date_string,
                "%Y-%m-%d"
            ).date()

        except (ValueError, TypeError):

            flash(
                "Please enter valid income details.",
                "danger"
            )

            return redirect(
                url_for("income")
            )

        new_income = Income(
            amount=amount,
            source=source,
            description=description,
            date=income_date,
            user_id=current_user.id
        )

        db.session.add(new_income)
        db.session.commit()

        flash(
            "Income added successfully.",
            "success"
        )

        return redirect(
            url_for("income")
        )

    incomes = Income.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Income.date.desc()
    ).all()

    return render_template(
        "income.html",
        incomes=incomes
    )


@app.route("/income/delete/<int:id>")
@login_required
def delete_income(id):

    income_item = Income.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(income_item)
    db.session.commit()

    flash(
        "Income deleted.",
        "success"
    )

    return redirect(
        url_for("income")
    )


# =========================================================
# BUDGET
# =========================================================

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():

    current_month = datetime.now().strftime(
        "%Y-%m"
    )

    if request.method == "POST":

        month = request.form.get(
            "month"
        )

        amount = request.form.get(
            "amount"
        )

        try:

            amount = float(amount)

            if amount <= 0:
                raise ValueError

        except (ValueError, TypeError):

            flash(
                "Enter a valid budget amount.",
                "danger"
            )

            return redirect(
                url_for("budget")
            )

        existing_budget = Budget.query.filter_by(
            user_id=current_user.id,
            month=month
        ).first()

        if existing_budget:

            existing_budget.amount = amount

        else:

            new_budget = Budget(
                month=month,
                amount=amount,
                user_id=current_user.id
            )

            db.session.add(new_budget)

        db.session.commit()

        flash(
            "Budget saved successfully.",
            "success"
        )

        return redirect(
            url_for("budget")
        )

    budgets = Budget.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Budget.month.desc()
    ).all()

    return render_template(
        "budget.html",
        budgets=budgets,
        current_month=current_month
    )


@app.route("/budget/delete/<int:id>")
@login_required
def delete_budget(id):

    budget_item = Budget.query.filter_by(
        id=id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(budget_item)
    db.session.commit()

    flash(
        "Budget deleted.",
        "success"
    )

    return redirect(
        url_for("budget")
    )


# =========================================================
# API FOR CHART DATA
# =========================================================

@app.route("/api/category-expenses")
@login_required
def category_expenses():

    data = db.session.query(
        Expense.category,
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == current_user.id
    ).group_by(
        Expense.category
    ).all()

    return jsonify({
        "labels": [
            item[0]
            for item in data
        ],
        "values": [
            float(item[1])
            for item in data
        ]
    })


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

with app.app_context():
    db.create_all()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )