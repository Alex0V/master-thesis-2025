package com.example.recipeapp.ui.navigation

sealed class Screen(val route: String) {
    object Auth : Screen("auth_screen")
    object Home : Screen("home_screen")

    object RecipeDetails : Screen("recipe_details/{recipeId}") {
        // Допоміжна функція, щоб створити лінк: "recipe_details/7281"
        fun createRoute(recipeId: Int) = "recipe_details/$recipeId"
    }
}