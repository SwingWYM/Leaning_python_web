if (!String.prototype.trim) {
	String.prototype.trim = function () {
		return this.replace(/^\s+|\s+$/g,'')
	}
}

$(function(){
	console.log('Extens $form...');
	$.fn.extend({//扩展jquery的插件
		showFormError:function(err){
			
		}
	})
})