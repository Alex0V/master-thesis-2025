package com.example.recipeapp.ui.screens

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.ui.navigation.BottomNavItem

@Composable
fun MainScreen(
    // Параметри для передачі в дочірні екрани
    tokenManager: TokenManager,
    apiService: RecipeApiService,
    onLogout: () -> Unit, // Колбек для виходу
    rootNavController: NavHostController
) {
    // 👇 Свій власний контролер навігації ТІЛЬКИ для вкладок
    val bottomNavController = rememberNavController()

    val items = listOf(
        BottomNavItem.Home,
        BottomNavItem.Search,
        BottomNavItem.Favorites,
        BottomNavItem.Profile
    )

    Scaffold(
        bottomBar = {
            NavigationBar {
                // Дізнаємось поточний маршрут, щоб підсвітити кнопку
                val navBackStackEntry by bottomNavController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination

                items.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = null) },
                        label = { Text(screen.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            bottomNavController.navigate(screen.route) {
                                // Щоб при натисканні "Назад" не проходити по всіх вкладках,
                                // а одразу виходити з додатка (або йти на Home)
                                popUpTo(bottomNavController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                // Щоб не відкривати той самий екран 10 разів
                                launchSingleTop = true
                                // Зберігаємо стан скролу
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        // 👇 Вкладений NavHost (всередині Scaffold)
        NavHost(
            navController = bottomNavController,
            startDestination = BottomNavItem.Home.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            // Вкладка 1: Рецепти
            composable(BottomNavItem.Home.route) {
                // Тут викликаємо наш старий RecipeScreen
                // ⚠️ Важливо: Приберіть з RecipeScreen кнопку Logout у TopBar, бо вона тепер у Profile
                FeedScreen(
                    navController = rootNavController, // або null, якщо там навігація не треба
                    apiService = apiService
                )
            }

            // Вкладка 2: Пошук
            composable(BottomNavItem.Search.route) {
                SearchScreen(
                    navController = rootNavController,
                    apiService = apiService
                )
                //Text("Екран пошуку", modifier = Modifier.padding(top = 50.dp))
            }

            // Вкладка 3: Улюблене
            composable(BottomNavItem.Favorites.route) {
                FavoritesScreen(
                    navController = rootNavController,
                    apiService = apiService
                )
            }

            // Вкладка 4: Профіль
            composable(BottomNavItem.Profile.route) {
                ProfileScreen(
                    navController = rootNavController,
                    apiService = apiService,
                    onLogout = onLogout
                )
            }
        }
    }
}