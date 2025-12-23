package com.example.recipeapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.recipeapp.data.api.RetrofitClient
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.ui.navigation.Screen
import com.example.recipeapp.ui.screens.AuthScreen
import com.example.recipeapp.ui.screens.MainScreen
import com.example.recipeapp.ui.screens.RecipeDetailScreen
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    val context = LocalContext.current

                    val tokenManager = remember { TokenManager(context) }
                    val retrofitClient = remember { RetrofitClient(tokenManager) }
                    val apiService = retrofitClient.api

                    // Стан завантаження початкового токена
                    var isTokenLoaded by remember { mutableStateOf(false) }
                    var startDestination by remember { mutableStateOf(Screen.Auth.route) }

                    // Глобальне спостереження за токеном
                    val accessTokenState = tokenManager.accessToken.collectAsState(initial = null)
                    val accessToken = accessTokenState.value

                    // Перевірка при запуску (Splash)
                    LaunchedEffect(Unit) {
                        val token = tokenManager.accessToken.first()
                        if (!token.isNullOrBlank()) {
                            startDestination = Screen.Home.route
                        } else {
                            startDestination = Screen.Auth.route
                        }
                        isTokenLoaded = true
                    }

                    if (!isTokenLoaded) {
                        // Спіннер тільки при "холодному" старті
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    } else {
                        NavHost(
                            navController = navController,
                            startDestination = startDestination,
                            // 👇 1. Плавний вхід (коли йдемо вперед)
                            enterTransition = { fadeIn(animationSpec = tween(500)) },
                            // 👇 2. Плавний вихід (коли йдемо вперед)
                            exitTransition = { fadeOut(animationSpec = tween(500)) },
                            // 👇 3. ВАЖЛИВО: Плавна поява AuthScreen при викиданні
                            popEnterTransition = { fadeIn(animationSpec = tween(500)) },
                            // 👇 4. ВАЖЛИВО: Плавне зникнення RecipeScreen при викиданні
                            popExitTransition = { fadeOut(animationSpec = tween(500)) }
                        ) {
                            // --- AUTH SCREEN ---
                            composable(Screen.Auth.route) {
                                // Авто-вхід
                                LaunchedEffect(accessToken) {
                                    if (!accessToken.isNullOrBlank()) {
                                        navController.navigate(Screen.Home.route) {
                                            popUpTo(Screen.Auth.route) { inclusive = true }
                                        }
                                    }
                                }
                                AuthScreen(navController, tokenManager, apiService)
                            }

                            // --- RECIPE SCREEN (Тепер це MAIN SCREEN) ---
                            composable(Screen.Home.route) {
                                // Авто-вихід
                                LaunchedEffect(accessToken) {
                                    if (accessToken == null) {
                                        navController.navigate(Screen.Auth.route) {
                                            popUpTo(0) { inclusive = true }
                                        }
                                    }
                                }

                                if (accessToken != null) {
                                    // 👇 ЗАМІСТЬ RecipeScreen ВИКЛИКАЄМО MainScreen
                                    MainScreen(
                                        tokenManager = tokenManager,
                                        apiService = apiService,
                                        onLogout = {
                                            // Тут реалізуємо логіку виходу, яку ми раніше писали в RecipeScreen
                                            // Але краще це робити через ViewModel профілю.
                                            // Для швидкого тесту поки можна так:
                                            val scope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO)
                                            scope.launch {
                                                // ... логіка logout API ...
                                                tokenManager.clearTokens()
                                                // Навігація спрацює автоматично через LaunchedEffect вище
                                            }
                                        },
                                        rootNavController = navController
                                    )
                                } else {
                                    Box(Modifier.fillMaxSize())
                                }
                            }

                            // 👇 ДОДАЄМО ЕКРАН ДЕТАЛЕЙ
                            composable(
                                route = Screen.RecipeDetails.route,
                                arguments = listOf(
                                    navArgument("recipeId") { type = NavType.IntType } // Кажемо, що це число
                                )
                            ) { backStackEntry ->
                                // 1. Витягуємо ID з аргументів
                                val recipeId = backStackEntry.arguments?.getInt("recipeId") ?: 0

                                // 2. Відкриваємо екран
                                RecipeDetailScreen(
                                    recipeId = recipeId,
                                    apiService = apiService,   // Ваш Retrofit сервіс (створений в MainActivity)
                                    onBack = { navController.popBackStack() } // Кнопка "Назад" повертає в стрічку
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}