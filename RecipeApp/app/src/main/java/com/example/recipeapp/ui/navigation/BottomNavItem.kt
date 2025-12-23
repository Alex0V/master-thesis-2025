package com.example.recipeapp.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.ui.graphics.vector.ImageVector

sealed class BottomNavItem(val route: String, val title: String, val icon: ImageVector) {
    object Home : BottomNavItem("home", "Рецепти", Icons.Default.Home)
    object Search : BottomNavItem("search", "Пошук", Icons.Default.Search)
    object Favorites : BottomNavItem("favorites", "Улюблене", Icons.Default.Favorite)
    object Profile : BottomNavItem("profile", "Профіль", Icons.Default.Person)
}