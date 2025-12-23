package com.example.recipeapp.ui.screens
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
//import androidx.compose.material.icons.filled.FavoriteBorder // Або outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.FavoriteBorder // Краще використовувати цей варіант
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.model.Nutrition
import com.example.recipeapp.viewmodel.RecipeDetailViewModel
import com.example.recipeapp.viewmodel.RecipeDetailViewModelFactory
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecipeDetailScreen(
    recipeId: Int,
    apiService: RecipeApiService,
    onBack: () -> Unit
) {
    val viewModel: RecipeDetailViewModel = viewModel(
        factory = RecipeDetailViewModelFactory(apiService)
    )

    LaunchedEffect(recipeId) {
        viewModel.loadRecipe(recipeId)
    }

    val recipe by viewModel.recipe.collectAsState()
    val isFavorite by viewModel.isFavorite.collectAsState() // Слідкуємо за лайком
    val isLoading by viewModel.isLoading.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {},
                navigationIcon = {
                    IconButton(
                        onClick = onBack,
                        colors = IconButtonDefaults.iconButtonColors(containerColor = Color.White.copy(alpha = 0.7f))
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent)
            )
        },
        // ДОДАЄМО КНОПКУ ЛАЙКА ТУТ
        floatingActionButton = {
            if (!isLoading && recipe != null) {
                FloatingActionButton(
                    onClick = { viewModel.toggleFavorite() },
                    containerColor = MaterialTheme.colorScheme.primary, // Колір кнопки
                    contentColor = Color.White,
                    shape = CircleShape
                ) {
                    // Анімована зміна іконки (за бажанням можна додати Crossfade)
                    Icon(
                        imageVector = if (isFavorite) Icons.Default.Favorite else Icons.Outlined.FavoriteBorder,
                        contentDescription = "Улюблене",
                        tint = if (isFavorite) Color.Red else Color.White // Червоне, якщо активне
                    )
                }
            }
        }
    ) { padding ->
        if (isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (recipe != null) {
            val item = recipe!!

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
            ) {
                // 1. ВЕЛИКА КАРТИНКА (Заходить під TopBar завдяки padding values scaffold, але тут ми ігноруємо верхній паддінг для ефекту)
                Box {
                    AsyncImage(
                        model = ImageRequest.Builder(LocalContext.current)
                            .data(item.imageUrl) // Оновлено поле з image_s3_path на imageUrl (якщо ви змінили модель)
                            .crossfade(true)
                            .build(),
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(300.dp)
                    )
                }

                Column(modifier = Modifier.padding(16.dp)) {
                    // 2. НАЗВА
                    Text(
                        text = item.title,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    // 3. ОСНОВНА ІНФО (Час, Складність, Порції)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        InfoBadge("⏱ ${item.totalTime} хв")
                        InfoBadge("📊 ${item.difficulty}")
                        InfoBadge("👥 ${formatAmount(item.portions ?: 1.0)} порц.")
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    // 4. НУТРІЄНТИ (БЖВ)
                    item.nutrition?.let { nutrition ->
                        NutritionSection(nutrition)
                        Spacer(modifier = Modifier.height(24.dp))
                    }

                    // ==========================================
                    // 5. ІНГРЕДІЄНТИ (ЗМІНЕНО ПІД СЕКЦІЇ)
                    // ==========================================
                    Text("Інгредієнти", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))

                    // Проходимось по СЕКЦІЯХ, а не по інгредієнтах напряму
                    item.sections.forEach { section ->

                        // Логіка показу заголовка: якщо секцій > 1 АБО назва не "Основне"
                        val showHeader = item.sections.size > 1 ||
                                (section.name != "Основне" && section.name != "Основні")

                        if (showHeader) {
                            Text(
                                text = section.name,
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(top = 12.dp, bottom = 4.dp)
                            )
                        }

                        // Список інгредієнтів всередині секції
                        section.items.forEach { ingredient ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "• ${ingredient.name}",
                                    style = MaterialTheme.typography.bodyLarge,
                                    modifier = Modifier.weight(1f) // Щоб назва не налазила на цифри
                                )
                                Text(
                                    // Форматуємо: 1.0 -> "1", 1.5 -> "1.5" + одиниця виміру
                                    text = "${formatAmount(ingredient.amount)} ${ingredient.unit}",
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyLarge
                                )
                            }
                            if (ingredient.isOptional) {
                                Text("(за бажанням)", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                            }
                            HorizontalDivider(modifier = Modifier.padding(top = 4.dp), color = Color.LightGray.copy(alpha = 0.3f))
                        }
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    // 6. ІНСТРУКЦІЯ
                    Text("Приготування", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(16.dp))

                    item.instructions.forEach { step ->
                        StepItem(stepNumber = step.stepNumber, title = step.title, description = step.description)
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    // Відступ знизу
                    Spacer(modifier = Modifier.height(30.dp))
                }
            }
        }
    }
}

// --- ДОПОМІЖНІ КОМПОНЕНТИ (Без змін) ---

@Composable
fun InfoBadge(text: String) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        shape = RoundedCornerShape(8.dp)
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSecondaryContainer
        )
    }
}

@Composable
fun NutritionSection(nutrition: Nutrition) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFF5F5F5), RoundedCornerShape(12.dp))
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        NutritionItem(value = "${nutrition.calories.toInt()}", label = "ккал")
        NutritionItem(value = "${nutrition.proteins}", label = "білки")
        NutritionItem(value = "${nutrition.fats}", label = "жири")
        NutritionItem(value = "${nutrition.carbs}", label = "вугл.")
    }
}

@Composable
fun NutritionItem(value: String, label: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = value, fontWeight = FontWeight.Black, style = MaterialTheme.typography.titleMedium)
        Text(text = label, style = MaterialTheme.typography.labelSmall, color = Color.Gray)
    }
}

@Composable
fun StepItem(stepNumber: Int, title: String?, description: String) {
    Row(verticalAlignment = Alignment.Top) {
        Box(
            modifier = Modifier
                .size(28.dp)
                .background(MaterialTheme.colorScheme.primary, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Text(text = "$stepNumber", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }

        Spacer(modifier = Modifier.width(12.dp))

        Column {
            title?.let {
                Text(text = it, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            }
            Text(
                text = description,
                style = MaterialTheme.typography.bodyLarge,
                lineHeight = 24.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
            )
        }
    }
}

// Функція форматування чисел (щоб прибрати .0)
fun formatAmount(amount: Double): String {
    if (amount <= 0.01) return ""
    return if (amount % 1.0 == 0.0) {
        amount.toInt().toString()
    } else {
        String.format(Locale.US, "%.1f", amount)
    }
}