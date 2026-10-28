import os
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)


# Connect to the Dishcovery database
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# Display the homepage
@app.route("/")

def home():
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM Recipes")
        recipe_count = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT recipe_id, recipe_name, cooking_time, difficulty
            FROM Recipes
            ORDER BY recipe_name
        """)
        recipes = cursor.fetchall()

        cursor.execute("""
            SELECT ingredient_id, ingredient_name
            FROM Ingredients
            ORDER BY ingredient_name
        """)
        ingredients = cursor.fetchall()

        cursor.execute("""
            SELECT category_id, category_name
            FROM Categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        cursor.close()

        return render_template(
            "index.html",
            recipe_count=recipe_count,
            recipes=recipes,
            ingredients=ingredients,
            categories=categories
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load the homepage.")
        return "Unable to retrieve recipes. Please check the database connection.", 500

    finally:
        if connection is not None and connection.is_connected():
            connection.close()




# Find recipes using available ingredients
@app.route("/find-recipes", methods=["POST"])
def find_recipes():
    data = request.get_json(silent=True) or {}
    ingredients = data.get("ingredients", [])

    if not isinstance(ingredients, list):
        return jsonify({"error": "Ingredients must be provided as a list."}), 400

    ingredients = list(dict.fromkeys(
        item.strip().lower()
        for item in ingredients
        if isinstance(item, str) and item.strip()
    ))
    if not ingredients:
        return jsonify({"error": "Please select at least one ingredient."}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(ingredients))

        query = f"""
            SELECT
                r.recipe_id,
                r.recipe_name,
                r.cooking_time,
                r.difficulty,
                COUNT(DISTINCT CASE
                    WHEN LOWER(i.ingredient_name) IN ({placeholders})
                    THEN i.ingredient_id
                END) AS matched_count,
                COUNT(DISTINCT ri.ingredient_id) AS total_ingredients,
                COUNT(DISTINCT CASE
                    WHEN LOWER(i.ingredient_name) NOT IN ({placeholders})
                    THEN i.ingredient_id
                END) AS missing_count,
                GROUP_CONCAT(
                    DISTINCT CASE
                        WHEN LOWER(i.ingredient_name) NOT IN ({placeholders})
                        THEN i.ingredient_name
                    END
                    ORDER BY i.ingredient_name
                    SEPARATOR ', '
                ) AS missing_ingredients
            FROM Recipes r
            JOIN Recipe_Ingredients ri ON r.recipe_id = ri.recipe_id
            JOIN Ingredients i ON ri.ingredient_id = i.ingredient_id
            GROUP BY r.recipe_id, r.recipe_name, r.cooking_time, r.difficulty
            HAVING matched_count > 0
            ORDER BY
                (matched_count = total_ingredients) DESC,
                matched_count DESC,
                r.recipe_name
        """
        cursor.execute(query, ingredients + ingredients + ingredients)
        recipes = cursor.fetchall()
        cursor.close()
        return jsonify({"recipes": recipes})
    except mysql.connector.Error:
        app.logger.exception("Recipe search failed.")
        return jsonify({"error": "Unable to search recipes right now."}), 500
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# Find recipes by category
@app.route("/category/<category_name>")
def find_by_category(category_name):
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.recipe_id, r.recipe_name, r.cooking_time, r.difficulty
            FROM Recipes r
            JOIN Recipe_Categories rc ON r.recipe_id = rc.recipe_id
            JOIN Categories c ON rc.category_id = c.category_id
            WHERE LOWER(c.category_name) = LOWER(%s)
            ORDER BY r.recipe_name
        """, (category_name,))
        recipes = cursor.fetchall()
        cursor.close()
        return render_template(
            "recipe_results.html",
            category=category_name.title(),
            recipes=recipes
        )
    except mysql.connector.Error:
        app.logger.exception("Category search failed.")
        return jsonify({"error": "Unable to retrieve recipes for this category."}), 500
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# Display individual recipe details
@app.route("/recipe/<int:recipe_id>")
def recipe_details(recipe_id):
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT recipe_id, recipe_name, cooking_time, difficulty, instructions
            FROM Recipes
            WHERE recipe_id = %s
        """, (recipe_id,))
        recipe = cursor.fetchone()
        if recipe is None:
            cursor.close()
            return "Recipe not found.", 404

        cursor.execute("""
            SELECT i.ingredient_name
            FROM Ingredients i
            JOIN Recipe_Ingredients ri ON i.ingredient_id = ri.ingredient_id
            WHERE ri.recipe_id = %s
            ORDER BY i.ingredient_name
        """, (recipe_id,))
        ingredients = cursor.fetchall()
        cursor.close()
        return render_template(
            "recipe_details.html",
            recipe=recipe,
            ingredients=ingredients
        )
    except mysql.connector.Error:
        app.logger.exception("Could not retrieve recipe details.")
        return "Unable to retrieve recipe details.", 500
    finally:
        if connection is not None and connection.is_connected():
            connection.close()



@app.route("/add-ingredient", methods=["POST"])
def add_ingredient():
    connection = None
    cursor = None

    try:
        data = request.get_json(silent=True) or {}
        ingredient_name = data.get("ingredient_name", "").strip()

        if not ingredient_name:
            return {"success": False, "message": "Please enter an ingredient name."}, 400

        if len(ingredient_name) > 100:
            return {"success": False, "message": "Ingredient name must be 100 characters or fewer."}, 400

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Reuse an existing ingredient if its name already exists.
        cursor.execute("""
            SELECT ingredient_id, ingredient_name
            FROM Ingredients
            WHERE LOWER(ingredient_name) = LOWER(%s)
            LIMIT 1
        """, (ingredient_name,))

        ingredient = cursor.fetchone()

        if ingredient:
            return {
                "success": True,
                "exists": True,
                "ingredient_id": ingredient["ingredient_id"],
                "ingredient_name": ingredient["ingredient_name"],
                "message": "This ingredient already exists."
            }

        cursor.execute("""
            INSERT INTO Ingredients (ingredient_name)
            VALUES (%s)
        """, (ingredient_name,))

        ingredient_id = cursor.lastrowid
        connection.commit()

        return {
            "success": True,
            "exists": False,
            "ingredient_id": ingredient_id,
            "ingredient_name": ingredient_name,
            "message": "Ingredient added successfully!"
        }, 201

    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        app.logger.exception("Could not add ingredient.")
        return {
            "success": False,
            "message": "Unable to save the ingredient. Please try again."
        }, 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()




# Display the Add Recipe form and save submitted recipes
@app.route("/add-recipe", methods=["GET", "POST"])
def add_recipe_page():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            recipe_name = request.form.get("recipe_name", "").strip()
            cooking_time_raw = request.form.get("cooking_time", "").strip()
            difficulty = request.form.get("difficulty", "").strip()
            category_raw = request.form.get("category", "").strip()
            instructions = request.form.get("instructions", "").strip()
            ingredient_raw_ids = []

            for value in request.form.getlist("ingredients"):
                ingredient_raw_ids.extend(
                    item.strip() for item in value.split(",") if item.strip()
                )

            ingredient_raw_ids = list(dict.fromkeys(ingredient_raw_ids))

            if not all([recipe_name, cooking_time_raw, difficulty, category_raw, instructions]):
                return "Please complete all required fields.", 400
            if not ingredient_raw_ids:
                return "Please select at least one ingredient.", 400

            cooking_time = int(cooking_time_raw)
            category_id = int(category_raw)
            ingredient_ids = [int(item) for item in ingredient_raw_ids]

            if cooking_time < 1:
                return "Cooking time must be at least 1 minute.", 400
            if difficulty not in ("Easy", "Medium", "Hard"):
                return "Invalid difficulty selected.", 400

            cursor.execute(
                "SELECT category_id FROM Categories WHERE category_id = %s",
                (category_id,)
            )
            if cursor.fetchone() is None:
                return "Invalid category selected.", 400

            placeholders = ", ".join(["%s"] * len(ingredient_ids))
            cursor.execute(
                f"SELECT ingredient_id FROM Ingredients WHERE ingredient_id IN ({placeholders})",
                tuple(ingredient_ids)
            )
            valid_ingredients = cursor.fetchall()
            if len(valid_ingredients) != len(set(ingredient_ids)):
                return "One or more selected ingredients are invalid.", 400

            cursor.execute("""
                INSERT INTO Recipes
                    (recipe_name, cooking_time, difficulty, instructions, is_user_added)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (recipe_name, cooking_time, difficulty, instructions))
            recipe_id = cursor.lastrowid

            cursor.executemany("""
                INSERT INTO Recipe_Ingredients (recipe_id, ingredient_id)
                VALUES (%s, %s)
            """, [(recipe_id, ingredient_id) for ingredient_id in ingredient_ids])

            cursor.execute("""
                INSERT INTO Recipe_Categories (recipe_id, category_id)
                VALUES (%s, %s)
            """, (recipe_id, category_id))

            connection.commit()
            return redirect(url_for("my_recipes"))

        # GET request: load form options from the database
        cursor.execute("""
            SELECT ingredient_id, ingredient_name
            FROM Ingredients
            ORDER BY ingredient_name
        """)
        ingredients = cursor.fetchall()
        cursor.execute("""
            SELECT category_id, category_name
            FROM Categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()
        return render_template(
            "add_recipe.html",
            ingredients=ingredients,
            categories=categories
        )

    except ValueError:
        if connection is not None and connection.is_connected():
            connection.rollback()
        return "Please enter a valid cooking time, category, and ingredient selection.", 400
    except mysql.connector.Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        app.logger.exception("Could not process the Add Recipe request.")
        return "Unable to process the recipe. Please check your entries and try again.", 500
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except mysql.connector.Error:
                pass
        if connection is not None and connection.is_connected():
            connection.close()


# Display recipes submitted through the Add Recipe form
@app.route("/my-recipes")
def my_recipes():
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.recipe_id, r.recipe_name, r.cooking_time, r.difficulty,
                   c.category_name
            FROM Recipes r
            LEFT JOIN Recipe_Categories rc ON r.recipe_id = rc.recipe_id
            LEFT JOIN Categories c ON rc.category_id = c.category_id
            WHERE r.is_user_added = TRUE
            ORDER BY r.recipe_name
        """)
        recipes = cursor.fetchall()
        cursor.close()
        return render_template("my_recipes.html", recipes=recipes)
    except mysql.connector.Error:
        app.logger.exception("Could not retrieve submitted recipes.")
        return "Unable to retrieve your recipes right now.", 500
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# Start the application
if __name__ == "__main__":
    app.run(debug=False)
