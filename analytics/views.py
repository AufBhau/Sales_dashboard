from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, Avg, F, FloatField
from django.db.models.functions import Cast
from .models import SalesData, CSVUpload
from .forms import CSVUploadForm, FilterForm
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
from datetime import datetime, timedelta
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials')
    return render(request, 'analytics/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def calculate_insights(current_data, comparison_data=None):
    """Generate smart insights from data"""
    insights = []
    
    if not current_data.exists():
        return insights
    
    # Current period metrics
    current_revenue = current_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
    current_leads = current_data.aggregate(Sum('leads'))['leads__sum'] or 0
    current_conversions = current_data.aggregate(Sum('conversions'))['conversions__sum'] or 0
    current_conv_rate = (current_conversions / current_leads * 100) if current_leads > 0 else 0
    
    # Best/Worst performers
    products = current_data.values('product').annotate(
        total=Sum('revenue')
    ).order_by('-total')
    
    if products:
        best_product = products[0]
        worst_product = products[len(products)-1]
        
        # Convert Decimal to float for comparisons
        best_total = float(best_product['total']) if best_product['total'] else 0
        worst_total = float(worst_product['total']) if worst_product['total'] else 0
        
        insights.append({
            'type': 'success',
            'icon': '🏆',
            'title': 'Top Performer',
            'message': f"{best_product['product']} leads with ${best_total:,.2f} in revenue"
        })
        
        if len(products) > 1 and worst_total < best_total * 0.3:
            insights.append({
                'type': 'warning',
                'icon': '⚠️',
                'title': 'Underperformer',
                'message': f"{worst_product['product']} needs attention (${worst_total:,.2f})"
            })
    
    # Regional insights - FIXED VERSION
    regions = current_data.values('region').annotate(
        total_leads=Sum('leads'),
        total_conversions=Sum('conversions'),
        total_revenue=Sum('revenue')
    )
    
    # Calculate conversion rate manually after aggregation
    region_list = []
    for region in regions:
        if region['total_leads'] and region['total_leads'] > 0:
            conv_rate = (region['total_conversions'] / region['total_leads']) * 100
            region_list.append({
                'region': region['region'],
                'conv_rate': conv_rate,
                'revenue': region['total_revenue']
            })
    
    # Sort by conversion rate
    region_list.sort(key=lambda x: x['conv_rate'], reverse=True)
    
    if region_list:
        best_region = region_list[0]
        insights.append({
            'type': 'info',
            'icon': '🌍',
            'title': 'Best Region',
            'message': f"{best_region['region']} has highest conversion rate at {best_region['conv_rate']:.1f}%"
        })
    
    # Conversion rate insight
    if current_conv_rate > 30:
        insights.append({
            'type': 'success',
            'icon': '🎯',
            'title': 'Excellent Conversion',
            'message': f"Your {current_conv_rate:.1f}% conversion rate is outstanding!"
        })
    elif current_conv_rate < 20:
        insights.append({
            'type': 'warning',
            'icon': '📉',
            'title': 'Low Conversion',
            'message': f"Conversion rate of {current_conv_rate:.1f}% could be improved"
        })
    
    # Comparison insights
    if comparison_data and comparison_data.exists():
        comp_revenue = comparison_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
        comp_leads = comparison_data.aggregate(Sum('leads'))['leads__sum'] or 0
        comp_conversions = comparison_data.aggregate(Sum('conversions'))['conversions__sum'] or 0
        
        # Convert to float for calculations
        comp_revenue = float(comp_revenue) if comp_revenue else 0
        comp_leads = float(comp_leads) if comp_leads else 0
        comp_conversions = float(comp_conversions) if comp_conversions else 0
        current_revenue_float = float(current_revenue) if current_revenue else 0
        current_leads_float = float(current_leads) if current_leads else 0
        
        if comp_revenue > 0:
            revenue_change = ((current_revenue_float - comp_revenue) / comp_revenue * 100)
            if abs(revenue_change) > 5:
                icon = '📈' if revenue_change > 0 else '📉'
                change_type = 'success' if revenue_change > 0 else 'danger'
                direction = 'up' if revenue_change > 0 else 'down'
                insights.append({
                    'type': change_type,
                    'icon': icon,
                    'title': f'Revenue {direction.title()}',
                    'message': f"Revenue {direction} {abs(revenue_change):.1f}% compared to previous period"
                })
        
        if comp_leads > 0:
            leads_change = ((current_leads_float - comp_leads) / comp_leads * 100)
            if abs(leads_change) > 10:
                icon = '🚀' if leads_change > 0 else '⬇️'
                change_type = 'info' if leads_change > 0 else 'warning'
                direction = 'up' if leads_change > 0 else 'down'
                insights.append({
                    'type': change_type,
                    'icon': icon,
                    'title': f'Lead Generation',
                    'message': f"Leads {direction} {abs(leads_change):.1f}% from previous period"
                })
    
    # Data freshness
    latest_date = current_data.order_by('-date').first()
    if latest_date:
        days_old = (datetime.now().date() - latest_date.date).days
        if days_old > 7:
            insights.append({
                'type': 'warning',
                'icon': '⏰',
                'title': 'Stale Data',
                'message': f"Latest data is {days_old} days old. Consider updating!"
            })
    
    return insights[:6]  # Return top 6 insights

@login_required
def dashboard(request):
    # Get comparison mode
    comparison_mode = request.GET.get('compare', '')
    
    # Get all sales data
    sales_data = SalesData.objects.all()
    comparison_data = None
    
    # Handle date presets
    preset = request.GET.get('preset', '')
    today = datetime.now().date()
    
    if preset == 'today':
        sales_data = sales_data.filter(date=today)
        if comparison_mode == 'previous':
            comparison_data = SalesData.objects.filter(date=today - timedelta(days=1))
    elif preset == 'last_7_days':
        sales_data = sales_data.filter(date__gte=today - timedelta(days=7))
        if comparison_mode == 'previous':
            comparison_data = SalesData.objects.filter(
                date__gte=today - timedelta(days=14),
                date__lt=today - timedelta(days=7)
            )
    elif preset == 'last_30_days':
        sales_data = sales_data.filter(date__gte=today - timedelta(days=30))
        if comparison_mode == 'previous':
            comparison_data = SalesData.objects.filter(
                date__gte=today - timedelta(days=60),
                date__lt=today - timedelta(days=30)
            )
    elif preset == 'this_month':
        sales_data = sales_data.filter(date__year=today.year, date__month=today.month)
        if comparison_mode == 'previous':
            last_month = today.replace(day=1) - timedelta(days=1)
            comparison_data = SalesData.objects.filter(
                date__year=last_month.year, 
                date__month=last_month.month
            )
    elif preset == 'last_month':
        last_month = today.replace(day=1) - timedelta(days=1)
        sales_data = sales_data.filter(date__year=last_month.year, date__month=last_month.month)
        if comparison_mode == 'previous':
            two_months_ago = (last_month.replace(day=1) - timedelta(days=1))
            comparison_data = SalesData.objects.filter(
                date__year=two_months_ago.year,
                date__month=two_months_ago.month
            )
    elif preset == 'this_year':
        sales_data = sales_data.filter(date__year=today.year)
        if comparison_mode == 'previous':
            comparison_data = SalesData.objects.filter(date__year=today.year - 1)
    
    # Apply custom filters
    filter_form = FilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['start_date']:
            sales_data = sales_data.filter(date__gte=filter_form.cleaned_data['start_date'])
        if filter_form.cleaned_data['end_date']:
            sales_data = sales_data.filter(date__lte=filter_form.cleaned_data['end_date'])
        if filter_form.cleaned_data['product']:
            sales_data = sales_data.filter(product__icontains=filter_form.cleaned_data['product'])
        if filter_form.cleaned_data['region']:
            sales_data = sales_data.filter(region__icontains=filter_form.cleaned_data['region'])
    
    # Calculate metrics
    total_revenue = sales_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
    total_leads = sales_data.aggregate(Sum('leads'))['leads__sum'] or 0
    total_conversions = sales_data.aggregate(Sum('conversions'))['conversions__sum'] or 0
    conversion_rate = (total_conversions / total_leads * 100) if total_leads > 0 else 0
    
    # Comparison metrics
    comp_metrics = None
    if comparison_data and comparison_data.exists():
        comp_revenue = comparison_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
        comp_leads = comparison_data.aggregate(Sum('leads'))['leads__sum'] or 0
        comp_conversions = comparison_data.aggregate(Sum('conversions'))['conversions__sum'] or 0
        comp_conv_rate = (comp_conversions / comp_leads * 100) if comp_leads > 0 else 0
        
        comp_metrics = {
            'revenue': comp_revenue,
            'leads': comp_leads,
            'conversions': comp_conversions,
            'conversion_rate': comp_conv_rate,
            'revenue_change': ((total_revenue - comp_revenue) / comp_revenue * 100) if comp_revenue > 0 else 0,
            'leads_change': ((total_leads - comp_leads) / comp_leads * 100) if comp_leads > 0 else 0,
            'conversions_change': ((total_conversions - comp_conversions) / comp_conversions * 100) if comp_conversions > 0 else 0,
            'conv_rate_change': conversion_rate - comp_conv_rate,
        }
    
    # Top Performers
    top_products = sales_data.values('product').annotate(
        total=Sum('revenue')
    ).order_by('-total')[:5]
    
    top_regions = sales_data.values('region').annotate(
        total=Sum('revenue')
    ).order_by('-total')[:5]
    
    # Generate Smart Insights
    insights = calculate_insights(sales_data, comparison_data)
    
    # Generate interactive Plotly charts
    charts = generate_plotly_charts(sales_data)
    
    context = {
        'total_revenue': total_revenue,
        'total_leads': total_leads,
        'total_conversions': total_conversions,
        'conversion_rate': round(conversion_rate, 2),
        'filter_form': filter_form,
        'charts': charts,
        'data_count': sales_data.count(),
        'top_products': top_products,
        'top_regions': top_regions,
        'current_preset': preset,
        'insights': insights,
        'comparison_mode': comparison_mode,
        'comp_metrics': comp_metrics,
    }
    return render(request, 'analytics/dashboard.html', context)

def generate_plotly_charts(queryset):
    """Generate interactive Plotly charts"""
    if not queryset.exists():
        return {}
    
    df = pd.DataFrame(list(queryset.values('date', 'product', 'region', 'revenue', 'leads', 'conversions')))
    charts = {}
    
    # 1. Revenue Trend (Line Chart)
    df_grouped = df.groupby('date')['revenue'].sum().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['date'],
        y=df_grouped['revenue'],
        mode='lines+markers',
        name='Revenue',
        line=dict(color='#3498db', width=3),
        marker=dict(size=8),
        hovertemplate='<b>Date:</b> %{x}<br><b>Revenue:</b> $%{y:,.2f}<extra></extra>'
    ))
    fig.update_layout(
        title='Revenue Over Time',
        xaxis_title='Date',
        yaxis_title='Revenue ($)',
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    charts['revenue_trend'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 2. Product Revenue (Bar Chart)
    product_revenue = df.groupby('product')['revenue'].sum().sort_values(ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=product_revenue.index,
        y=product_revenue.values,
        marker_color='#2ecc71',
        hovertemplate='<b>%{x}</b><br>Revenue: $%{y:,.2f}<extra></extra>'
    ))
    fig.update_layout(
        title='Revenue by Product',
        xaxis_title='Product',
        yaxis_title='Revenue ($)',
        height=400,
        template='plotly_white'
    )
    charts['product_revenue'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 3. Product Revenue Pie Chart
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=product_revenue.index,
        values=product_revenue.values,
        hovertemplate='<b>%{label}</b><br>Revenue: $%{value:,.2f}<br>Share: %{percent}<extra></extra>',
        textposition='inside',
        textinfo='percent+label'
    ))
    fig.update_layout(
        title='Revenue Distribution by Product',
        height=400,
        template='plotly_white'
    )
    charts['product_pie'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 4. Conversion Rate by Region
    region_data = df.groupby('region').agg({'leads': 'sum', 'conversions': 'sum'})
    region_data['conv_rate'] = (region_data['conversions'] / region_data['leads'] * 100).fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=region_data.index,
        y=region_data['conv_rate'],
        marker_color='#e74c3c',
        hovertemplate='<b>%{x}</b><br>Conversion Rate: %{y:.2f}%<extra></extra>'
    ))
    fig.update_layout(
        title='Conversion Rate by Region',
        xaxis_title='Region',
        yaxis_title='Conversion Rate (%)',
        height=400,
        template='plotly_white'
    )
    charts['region_conversion'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 5. Region Revenue Pie Chart
    region_revenue = df.groupby('region')['revenue'].sum()
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=region_revenue.index,
        values=region_revenue.values,
        hovertemplate='<b>%{label}</b><br>Revenue: $%{value:,.2f}<br>Share: %{percent}<extra></extra>',
        textposition='inside',
        textinfo='percent+label'
    ))
    fig.update_layout(
        title='Revenue Distribution by Region',
        height=400,
        template='plotly_white'
    )
    charts['region_pie'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # 6. Leads vs Conversions (Grouped Bar)
    product_data = df.groupby('product').agg({'leads': 'sum', 'conversions': 'sum'})
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Leads',
        x=product_data.index,
        y=product_data['leads'],
        marker_color='#3498db'
    ))
    fig.add_trace(go.Bar(
        name='Conversions',
        x=product_data.index,
        y=product_data['conversions'],
        marker_color='#2ecc71'
    ))
    fig.update_layout(
        title='Leads vs Conversions by Product',
        xaxis_title='Product',
        yaxis_title='Count',
        barmode='group',
        height=400,
        template='plotly_white'
    )
    charts['leads_conversions'] = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    return charts

@login_required
def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            
            try:
                df = pd.read_csv(csv_file)
                
                required_cols = ['date', 'product', 'region', 'revenue', 'leads', 'conversions']
                if not all(col in df.columns for col in required_cols):
                    messages.error(request, f'CSV must contain columns: {", ".join(required_cols)}')
                    return redirect('upload_csv')
                
                upload = form.save(commit=False)
                upload.user = request.user
                upload.save()
                
                rows_imported = 0
                for _, row in df.iterrows():
                    try:
                        SalesData.objects.create(
                            uploaded_by=request.user,
                            date=pd.to_datetime(row['date']).date(),
                            product=row['product'],
                            region=row['region'],
                            revenue=float(row['revenue']),
                            leads=int(row['leads']),
                            conversions=int(row['conversions'])
                        )
                        rows_imported += 1
                    except Exception as e:
                        continue
                
                upload.rows_imported = rows_imported
                upload.save()
                
                messages.success(request, f'Successfully imported {rows_imported} rows!')
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(request, f'Error processing CSV: {str(e)}')
                return redirect('upload_csv')
    else:
        form = CSVUploadForm()
    
    return render(request, 'analytics/upload.html', {'form': form})

@login_required
def export_report(request):
    sales_data = SalesData.objects.all()
    
    filter_form = FilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['start_date']:
            sales_data = sales_data.filter(date__gte=filter_form.cleaned_data['start_date'])
        if filter_form.cleaned_data['end_date']:
            sales_data = sales_data.filter(date__lte=filter_form.cleaned_data['end_date'])
        if filter_form.cleaned_data['product']:
            sales_data = sales_data.filter(product__icontains=filter_form.cleaned_data['product'])
        if filter_form.cleaned_data['region']:
            sales_data = sales_data.filter(region__icontains=filter_form.cleaned_data['region'])
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Product', 'Region', 'Revenue', 'Leads', 'Conversions', 'Conversion Rate'])
    
    for sale in sales_data:
        conv_rate = (sale.conversions / sale.leads * 100) if sale.leads > 0 else 0
        writer.writerow([
            sale.date,
            sale.product,
            sale.region,
            sale.revenue,
            sale.leads,
            sale.conversions,
            f"{conv_rate:.2f}%"
        ])
    
    return response

@login_required
def export_excel(request):
    sales_data = SalesData.objects.all()
    
    filter_form = FilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['start_date']:
            sales_data = sales_data.filter(date__gte=filter_form.cleaned_data['start_date'])
        if filter_form.cleaned_data['end_date']:
            sales_data = sales_data.filter(date__lte=filter_form.cleaned_data['end_date'])
        if filter_form.cleaned_data['product']:
            sales_data = sales_data.filter(product__icontains=filter_form.cleaned_data['product'])
        if filter_form.cleaned_data['region']:
            sales_data = sales_data.filter(region__icontains=filter_form.cleaned_data['region'])
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    
    headers = ['Date', 'Product', 'Region', 'Revenue', 'Leads', 'Conversions', 'Conversion Rate']
    ws.append(headers)
    
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    for sale in sales_data:
        conv_rate = (sale.conversions / sale.leads * 100) if sale.leads > 0 else 0
        ws.append([
            sale.date.strftime('%Y-%m-%d'),
            sale.product,
            sale.region,
            float(sale.revenue),
            sale.leads,
            sale.conversions,
            f"{conv_rate:.2f}%"
        ])
    
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    ws2 = wb.create_sheet("Summary")
    ws2['A1'] = "Metric"
    ws2['B1'] = "Value"
    ws2['A1'].font = header_font
    ws2['B1'].font = header_font
    
    total_revenue = sales_data.aggregate(Sum('revenue'))['revenue__sum'] or 0
    total_leads = sales_data.aggregate(Sum('leads'))['leads__sum'] or 0
    total_conversions = sales_data.aggregate(Sum('conversions'))['conversions__sum'] or 0
    conversion_rate = (total_conversions / total_leads * 100) if total_leads > 0 else 0
    
    ws2['A2'] = "Total Revenue"
    ws2['B2'] = float(total_revenue)
    ws2['A3'] = "Total Leads"
    ws2['B3'] = total_leads
    ws2['A4'] = "Total Conversions"
    ws2['B4'] = total_conversions
    ws2['A5'] = "Conversion Rate"
    ws2['B5'] = f"{conversion_rate:.2f}%"
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="sales_report_{datetime.now().strftime("%Y%m%d")}.xlsx"'
    wb.save(response)
    
    return response

@login_required
def delete_data(request):
    if request.method == 'POST':
        delete_type = request.POST.get('delete_type')
        
        if delete_type == 'all':
            count = SalesData.objects.all().count()
            SalesData.objects.all().delete()
            messages.success(request, f'Deleted all {count} records!')
        elif delete_type == 'filtered':
            sales_data = SalesData.objects.all()
            filter_form = FilterForm(request.POST)
            if filter_form.is_valid():
                if filter_form.cleaned_data['start_date']:
                    sales_data = sales_data.filter(date__gte=filter_form.cleaned_data['start_date'])
                if filter_form.cleaned_data['end_date']:
                    sales_data = sales_data.filter(date__lte=filter_form.cleaned_data['end_date'])
                if filter_form.cleaned_data['product']:
                    sales_data = sales_data.filter(product__icontains=filter_form.cleaned_data['product'])
                if filter_form.cleaned_data['region']:
                    sales_data = sales_data.filter(region__icontains=filter_form.cleaned_data['region'])
            
            count = sales_data.count()
            sales_data.delete()
            messages.success(request, f'Deleted {count} filtered records!')
        
        return redirect('dashboard')
    
    return render(request, 'analytics/delete_confirm.html')