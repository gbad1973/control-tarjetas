# tarjetas_app/forms.py
from django import forms
from .models import Persona, Tarjeta, Establecimiento, Movimiento

class PersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre', 'email', 'telefono']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nombre completo',
                'required': 'required'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control', 
                'placeholder': 'correo@ejemplo.com'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Teléfono'
            }),
        }
        labels = {
            'nombre': 'Nombre completo',
            'email': 'Correo Electrónico', 
            'telefono': 'Teléfono',
        }

class TarjetaForm(forms.ModelForm):
    # Campo personalizado para la fecha MM/AA
    fecha_vencimiento_tarjeta_mm_aa = forms.CharField(
        label='Fecha de vencimiento de tarjeta (MM/AA)',
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/AA',
            'pattern': '(0[1-9]|1[0-2])/([0-9]{2})'
        }),
        help_text='Formato: MM/AA (Ej: 12/25 para Diciembre 2025)'
    )
    
    class Meta:
        model = Tarjeta
        fields = ['numero', 'tipo', 'banco', 'titular', 'limite_credito', 
                 'fecha_vencimiento_pago', 'fecha_vencimiento_tarjeta_mm_aa']
        widgets = {
            'numero': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '1234 5678 9012 3456',
                'required': 'required'
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'banco': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nombre del banco',
                'required': 'required'
            }),
            'titular': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'limite_credito': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'min': '0',
                'required': 'required'
            }),
            'fecha_vencimiento_pago': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '1', 
                'max': '31',
                'required': 'required',
                'placeholder': '15'
            }),
        }
        labels = {
            'numero': 'Número de tarjeta',
            'tipo': 'Tipo de tarjeta',
            'banco': 'Banco',
            'titular': 'Titular',
            'limite_credito': 'Límite de crédito',
            'fecha_vencimiento_pago': 'Día de vencimiento de pago (1-31)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando, establecer el valor inicial para fecha_vencimiento_tarjeta_mm_aa
        if self.instance and self.instance.pk and self.instance.fecha_vencimiento_tarjeta:
            fecha_str = self.instance.fecha_vencimiento_tarjeta.strftime('%m/%y')
            self.initial['fecha_vencimiento_tarjeta_mm_aa'] = fecha_str
    
    def clean_fecha_vencimiento_tarjeta_mm_aa(self):
        data = self.cleaned_data['fecha_vencimiento_tarjeta_mm_aa']
        try:
            # Convertir MM/AA a fecha (asumiendo día 1 del mes)
            mes, ano = data.split('/')
            # Convertir AA a AAAA (asumiendo años 2000+)
            ano = int(ano) + 2000
            from datetime import date
            return date(ano, int(mes), 1)
        except (ValueError, AttributeError):
            raise forms.ValidationError('Formato incorrecto. Use MM/AA (Ej: 04/28)')

class EstablecimientoForm(forms.ModelForm):
    class Meta:
        model = Establecimiento
        fields = ['nombre', 'descripcion', 'porcentaje_cashback']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nombre del establecimiento'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Descripción'
            }),
            'porcentaje_cashback': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01'
            }),
        }
        labels = {
            'nombre': 'Nombre del establecimiento',
            'descripcion': 'Descripción',
            'porcentaje_cashback': 'Porcentaje de cashback (%)',
        }

class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ['tarjeta', 'persona', 'establecimiento', 'tipo', 'monto', 'descripcion', 'fecha']
        widgets = {
            'tarjeta': forms.Select(attrs={'class': 'form-control'}),
            'persona': forms.Select(attrs={'class': 'form-control'}),
            'establecimiento': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'tarjeta': 'Tarjeta',
            'persona': 'Persona',
            'establecimiento': 'Establecimiento',
            'tipo': 'Tipo de movimiento',
            'monto': 'Monto',
            'descripcion': 'Descripción',
            'fecha': 'Fecha del movimiento',
        }