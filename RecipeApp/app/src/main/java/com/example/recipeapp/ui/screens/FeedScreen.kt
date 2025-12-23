package com.example.recipeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.viewmodel.FeedViewModel
import com.example.recipeapp.viewmodel.FeedViewModelFactory
import com.example.recipeapp.ui.navigation.Screen
import com.example.recipeapp.ui.components.RecipeItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeedScreen(
    navController: NavController,
    apiService: RecipeApiService
) {
    val viewModel: FeedViewModel = viewModel(
        factory = FeedViewModelFactory(apiService)
    )

    val recipes by viewModel.recipes.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()

    // АВТОМАТИЧНЕ ОНОВЛЕННЯ
    // Цей код спрацьовує кожного разу, коли FeedScreen стає видимим (створюється)
    LaunchedEffect(Unit) {
        // Ми завжди перезавантажуємо рекомендації при вході на екран.
        // Це вирішує проблему з оновленням профілю без складних "сигналів".
        viewModel.loadRecommendations()
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Рекомендації на сьогодні",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )
                }
            )
        }
    ) { paddingValues ->

        // ❌ PullToRefreshBox ПРИБРАЛИ
        // Тепер тут просто Box, який займає екран
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            when {
                // 1. Індикатор завантаження (по центру, якщо список ще пустий)
                isLoading && recipes.isEmpty() -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }

                // 2. Помилка + Кнопка "Спробувати ще"
                error != null -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = error ?: "Помилка завантаження",
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(16.dp)
                        )
                        // Кнопка все ще потрібна, якщо немає інтернету
                        Button(onClick = { viewModel.loadRecommendations() }) {
                            Text("Спробувати ще раз")
                        }
                    }
                }

                // 3. Пустий список
                recipes.isEmpty() && !isLoading -> {
                    Text(
                        text = "На жаль, рецептів не знайдено",
                        modifier = Modifier.align(Alignment.Center)
                    )
                }

                // 4. Список рецептів
                else -> {
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        contentPadding = PaddingValues(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        items(items = recipes, key = { it.id }) { recipe ->
                            RecipeItem(
                                recipe = recipe,
                                onClick = {
                                    navController.navigate(Screen.RecipeDetails.createRoute(recipe.id))
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}