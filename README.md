# 🍽️ Dishcovery

**Discover recipes using the ingredients you have!**

Dishcovery is a database-driven web application that helps users find recipes based on available ingredients. It also allows users to add new ingredients and recipes to the database.

## ✨ Features

* Search and select available ingredients.
* Add new ingredients to the database.
* Find matching recipes and view missing ingredients.
* Sort recipes by cooking time and ingredient availability.
* Browse recipes by category.
* View cooking instructions and recipe details.
* Add and manage user-created recipes.

## 🛠️ Technologies

* **Frontend:** HTML, CSS, JavaScript
* **Backend:** Python, Flask
* **Database:** MySQL

## 🗄️ Database Tables

* `Recipes`
* `Ingredients`
* `Categories`
* `Recipe_Ingredients`
* `Recipe_Categories`

The project demonstrates relational database design, SQL queries, table relationships, data insertion, retrieval, filtering, and sorting.

## 🚀 Setup

1. Install Python and MySQL.

2. Install dependencies:

   ```bash
   pip install flask mysql-connector-python python-dotenv
   ```

3. Create the `dishcovery` database and required tables in MySQL.

4. Create an `app/.env` file with your database credentials:

   ```env
   DB_HOST=localhost
   DB_USER=your_mysql_username
   DB_PASSWORD=your_mysql_password
   DB_NAME=dishcovery
   ```

5. Run the application:

   ```bash
   cd app
   python app.py
   ```

6. Open `http://127.0.0.1:5000` in your browser.

**Note:** The database schema and sample data must be set up before running the application. Never upload your `.env` file or database credentials to GitHub.

## 🎯 Objective

To demonstrate practical DBMS concepts through an interactive recipe discovery and ingredient management system.

---

*Dishcovery — Discover, Cook, Enjoy!*
